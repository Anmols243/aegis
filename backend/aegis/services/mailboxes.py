"""Connected mailboxes: sign in, poll for new mail, tag verdicts, disconnect.

Mailboxes are linked with the provider's own sign-in (Google or Microsoft,
OAuth with PKCE). AEGIS never handles a mail password. The refresh token is
stored encrypted and decrypted only while in use; it is never logged or
returned.
"""
from __future__ import annotations

import os
import re
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import delete, func, select

from ..core import crypto
from ..core.config import get_settings
from ..core.logging import get_logger
from ..db.models import Analysis, Entity, Mailbox
from ..db.session import iso, session_scope
from ..providers import google, microsoft, oauth
from . import analysis as svc

log = get_logger("mailboxes")
OWNER_PLACEHOLDER = "[your address]"
PROVIDERS = {google.ID: google, microsoft.ID: microsoft}
SIGN_IN_PROVIDERS = [
    {"id": google.ID, "name": "Google", "covers": "Gmail and Google Workspace"},
    {"id": microsoft.ID, "name": "Microsoft",
     "covers": "Outlook.com, Hotmail, Live and Microsoft 365"},
]


def redact_owner(raw: str, owner_email: str) -> str:
    """Replace the mailbox owner's own address before anything is analyzed or stored."""
    return re.sub(re.escape(owner_email), OWNER_PLACEHOLDER, raw, flags=re.IGNORECASE)


def provider_list() -> list[dict]:
    st = get_settings()
    return [{**p, "supported": st.oauth_client(p["id"]) is not None} for p in SIGN_IN_PROVIDERS]


async def public(session, mb: Mailbox) -> dict:
    scanned = (await session.execute(select(func.count()).select_from(Analysis).where(
        Analysis.mailbox_id == mb.id))).scalar_one()
    flagged = (await session.execute(select(func.count()).select_from(Analysis).where(
        Analysis.mailbox_id == mb.id, Analysis.label.in_(("SCAM", "SUSPICIOUS"))))).scalar_one()
    prov = PROVIDERS.get(mb.provider)
    return {"id": mb.id, "provider": mb.provider, "email": mb.email, "host": mb.host,
            "status": mb.status, "last_checked_at": iso(mb.last_checked_at),
            "last_error": mb.last_error, "created_at": iso(mb.created_at), "scanned": scanned,
            "flagged": flagged, "label_mode": mb.label_mode, "retention_days": mb.retention_days,
            "manage_url": prov.MANAGE_URL if prov else None}


def _retention(value) -> int:
    try:
        retention = int(value)
    except (TypeError, ValueError):
        raise HTTPException(422, "retention_days must be a number") from None
    if retention not in (1, 7, 30):
        raise HTTPException(422, "retention_days must be 1, 7 or 30")
    return retention


async def _check_quota(owner_hash: str) -> None:
    async with session_scope() as s:
        count = (await s.execute(select(func.count()).select_from(Mailbox).where(
            Mailbox.owner_hash == owner_hash))).scalar_one()
        if count >= 5:
            raise HTTPException(409, "at most 5 mailboxes per browser")


def _provider(provider_id: str):
    prov = PROVIDERS.get(provider_id)
    if prov is None:
        raise HTTPException(404, "unknown sign-in provider")
    return prov


def _client_for(prov) -> tuple[str, str, str]:
    cfg = get_settings().oauth_client(prov.ID)
    if cfg is None:
        raise oauth.OAuthError(f"Sign in with {prov.NAME} is not set up on this server.")
    return cfg


# --------------------------------------------------------------------------- sign-in

def sign_in_start(provider_id: str, owner_hash: str, retention_days) -> dict:
    prov = _provider(provider_id)
    if get_settings().oauth_client(prov.ID) is None:
        raise HTTPException(503, f"Sign in with {prov.NAME} is not set up on this server")
    cid, _, redirect = _client_for(prov)
    url, state, pair = oauth.begin(prov, cid, redirect, owner_hash, _retention(retention_days))
    return {"url": url, "state": state, "pair": pair}


async def sign_in_callback(provider_id: str, viewer: str | None, code: str, state: str) -> str:
    """The provider sent the browser back. Exchange the code, then either connect
    right away (same browser that started) or wait for confirmation (another
    browser). Returns "connected" or "confirm"."""
    prov = _provider(provider_id)
    p = oauth.get_pending(state)
    if p["provider"] != prov.ID:
        raise oauth.OAuthError("This sign-in belongs to another provider. Please start again.")
    if p["status"] != "pending":
        raise oauth.OAuthError("This sign-in was already used. Please start again from AEGIS.")
    p["status"] = "exchanging"
    try:
        cid, secret, redirect = _client_for(prov)
        tok = await oauth.exchange(prov, cid, secret, redirect, code, p["verifier"])
        p["email"], p["cursor"] = await prov.profile(tok["access_token"])
    except oauth.OAuthError as e:
        p["status"], p["error"] = "error", str(e)
        raise
    except Exception:
        p["status"], p["error"] = "error", f"Could not reach {prov.NAME}. Please try again."
        raise
    p["refresh"] = tok["refresh_token"]
    if viewer is not None and secrets.compare_digest(viewer, p["owner"]):
        await _finish(p)
        return "connected"
    # A different browser (the app panel that started it cannot sign in to Google).
    # Never attach a mailbox to another session without an explicit confirmation
    # in the browser that holds the account.
    p["status"] = "confirm"
    return "confirm"


async def _finish(p: dict) -> dict:
    try:
        mb = await _save(p["provider"], p["owner"], p["refresh"], p["email"], p["cursor"],
                         p["retention"])
    except HTTPException as e:
        p["status"], p["error"] = "error", str(e.detail)
        raise
    finally:
        p.pop("refresh", None)
    p["status"], p["mailbox_id"] = "connected", mb["id"]
    return mb


async def sign_in_confirm(state: str, connect: bool) -> dict | None:
    """The browser that holds the account confirms (or cancels) attaching it to
    the AEGIS session that started the sign-in."""
    p = oauth.get_pending(state)
    if p["status"] != "confirm":
        raise HTTPException(409, "nothing to confirm for this sign-in")
    if not connect:
        refresh = p.pop("refresh", None)
        p["status"] = "cancelled"
        if refresh:
            await PROVIDERS[p["provider"]].revoke(refresh)
        return None
    p["status"] = "saving"
    return await _finish(p)


def sign_in_status(state: str, owner_hash: str) -> dict:
    """For the window that started the sign-in: how far it got."""
    try:
        p = oauth.get_pending(state)
    except oauth.OAuthError:
        return {"status": "expired"}
    if not secrets.compare_digest(p["owner"], owner_hash):
        raise HTTPException(404, "not found")
    return {"status": p["status"], "email": p.get("email"), "error": p.get("error")}


def sign_in_pairing(state: str) -> dict:
    """For the confirmation page in the browser the provider returned to."""
    p = oauth.get_pending(state)
    if p["status"] not in ("confirm", "saving", "connected", "cancelled", "error"):
        raise oauth.OAuthError("This sign-in is not waiting for confirmation.")
    return {"status": p["status"], "provider": p["provider"], "email": p.get("email"),
            "pair": p["pair"], "error": p.get("error")}


def mailbox_of(state: str) -> str | None:
    return oauth.get_pending(state).get("mailbox_id")


async def _save(provider_id: str, owner_hash: str, refresh: str, email: str, cursor: int,
                retention: int) -> dict:
    """Connect (or reconnect) an account for this owner."""
    prov = PROVIDERS[provider_id]
    async with session_scope() as s:
        mb = (await s.execute(select(Mailbox).where(
            Mailbox.owner_hash == owner_hash, Mailbox.provider == prov.ID,
            Mailbox.email == email))).scalar_one_or_none()
        if mb is None:
            await _check_quota(owner_hash)
            mb = Mailbox(id=svc.new_id("mb"), owner_hash=owner_hash, provider=prov.ID,
                         email=email, host=prov.HOST, port=443, label_mode=prov.LABEL_MODE,
                         uidvalidity=None)
            s.add(mb)
        mb.secret = crypto.encrypt(refresh, mb.id)
        mb.status, mb.last_error = "active", None
        mb.last_uid = cursor                    # new mail only, from this moment
        mb.retention_days = retention
        mb.last_checked_at = datetime.now(timezone.utc)
        await s.flush()
        oauth.forget(mb.id)
        log.info("mailbox connected", extra={"mailbox_id": mb.id, "provider": prov.ID})
        return await public(s, mb)


async def owned(session, mailbox_id: str, owner_hash: str) -> Mailbox:
    mb = await session.get(Mailbox, mailbox_id[:40])
    if mb is None or mb.owner_hash != owner_hash:
        raise HTTPException(404, "not found")
    return mb


# --------------------------------------------------------------------------- mail

async def _token(mb_id: str) -> tuple[object, str]:
    """(provider module, access token). Stores a rotated refresh token."""
    async with session_scope() as s:
        mb = await s.get(Mailbox, mb_id)
        prov = PROVIDERS[mb.provider]
        refresh = crypto.decrypt(mb.secret, mb.id)
    cid, secret, _ = _client_for(prov)
    token, rotated = await oauth.access_token(prov, mb_id, cid, secret, refresh)
    if rotated:
        async with session_scope() as s:
            mb = await s.get(Mailbox, mb_id)
            if mb is not None:
                mb.secret = crypto.encrypt(rotated, mb.id)
    return prov, token


def _external_id(mailbox_id: str, message_id: str) -> str:
    return f"oa:{mailbox_id}:{message_id}"


async def poll(mailbox_id: str) -> int:
    """Fetch new mail for one mailbox and queue it. Returns the number queued."""
    limit = get_settings().mailbox_max_per_poll
    async with session_scope() as s:
        mb = await s.get(Mailbox, mailbox_id)
        if mb is None or mb.status == "paused":
            return 0
        if mb.provider not in PROVIDERS:
            mb.status = "error"
            mb.last_error = ("App-password mailboxes are no longer supported. Disconnect and "
                             "sign in with Google or Microsoft.")
            return 0
        email, owner, cursor = mb.email, mb.owner_hash, mb.last_uid
    error, msgs, new_cursor = None, [], cursor
    try:
        prov, token = await _token(mailbox_id)
        ids, new_cursor = await prov.new_message_ids(token, cursor, limit)
        async with session_scope() as s:
            seen = set((await s.execute(select(Analysis.external_id).where(
                Analysis.external_id.in_([_external_id(mailbox_id, i) for i in ids])
            ))).scalars())
        for mid in ids:
            if _external_id(mailbox_id, mid) not in seen:
                msgs.append((mid, await prov.raw_message(token, mid)))
    except oauth.OAuthError as e:
        error = str(e)
    except Exception as e:  # noqa: BLE001 - network blips
        error = f"temporary error: {type(e).__name__}"
    queued = 0
    async with session_scope() as s:
        mb = await s.get(Mailbox, mailbox_id)
        if mb is None:
            return 0
        mb.last_checked_at = datetime.now(timezone.utc)
        if error:
            mb.status, mb.last_error = "error", error[:300]
            return 0
        mb.status, mb.last_error = ("active" if mb.status != "paused" else "paused"), None
        mb.last_uid = new_cursor
        for mid, raw in msgs:
            if not raw:
                continue        # too large: skipped, the cursor still moves past it
            await svc.create(s, source="mailbox",
                             raw=redact_owner(raw.decode("utf-8", "replace"), email),
                             external_id=_external_id(mailbox_id, mid), owner_hash=owner,
                             mailbox_id=mailbox_id)
            queued += 1
    return queued


async def label_verdict(analysis_id: str) -> None:
    """After a mailbox email is analyzed, tag it in the mailbox (SCAM / SUSPICIOUS only)."""
    async with session_scope() as s:
        a = await s.get(Analysis, analysis_id)
        if (a is None or not a.mailbox_id or a.labeled_at or a.status != "done"
                or a.label not in ("SCAM", "SUSPICIOUS") or not a.external_id
                or not a.external_id.startswith("oa:")):
            return
        mb = await s.get(Mailbox, a.mailbox_id)
        if mb is None or mb.status == "paused" or mb.provider not in PROVIDERS:
            return
        message_id, label = a.external_id.split(":", 2)[2], a.label
    try:
        prov, token = await _token(mb.id)
        await prov.apply_label(token, message_id, label)
    except Exception as e:  # noqa: BLE001 - labeling is best effort
        log.warning("label failed", extra={"analysis_id": analysis_id, "error": str(e)[:200]})
        return
    async with session_scope() as s:
        a = await s.get(Analysis, analysis_id)
        a.labeled_at = datetime.now(timezone.utc)


async def remove(mailbox_id: str, owner_hash: str, purge: bool) -> None:
    async with session_scope() as s:
        mb = await owned(s, mailbox_id, owner_hash)
        if purge:
            ids = (await s.execute(select(Analysis.id).where(
                Analysis.mailbox_id == mb.id))).scalars().all()
            if ids:
                await s.execute(delete(Entity).where(Entity.analysis_id.in_(ids)))
                await s.execute(delete(Analysis).where(Analysis.id.in_(ids)))
                for aid in ids:
                    path = svc.screenshot_path(get_settings(), aid)
                    if os.path.exists(path):
                        os.remove(path)
        prov = PROVIDERS.get(mb.provider)
        refresh = None
        if prov is not None:
            try:
                refresh = crypto.decrypt(mb.secret, mb.id)
            except Exception:  # noqa: BLE001
                refresh = None
        await s.delete(mb)
    oauth.forget(mailbox_id)
    if prov is not None and refresh:
        await prov.revoke(refresh)    # Google: access ends at Google too
    log.info("mailbox removed", extra={"mailbox_id": mailbox_id, "purged": purge})
