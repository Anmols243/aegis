"""Connected mailboxes: connect, poll for new mail, label verdicts, disconnect.

All IMAP work runs in a thread (imaplib is blocking). Credentials are
decrypted only for the duration of a session and never logged or returned.
"""
from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import delete, func, select

from ..core import crypto
from ..core.config import get_settings
from ..core.logging import get_logger
from ..db.models import Analysis, Entity, Mailbox
from ..db.session import iso, session_scope
from ..providers import imap
from . import analysis as svc

log = get_logger("mailboxes")
_EMAIL = re.compile(r"^[^@\s]{1,64}@[A-Za-z0-9.-]{1,255}\.[A-Za-z]{2,}$")
_HOST = re.compile(r"^(?=.{1,253}$)([A-Za-z0-9-]{1,63}\.)+[A-Za-z]{2,63}$")
OWNER_PLACEHOLDER = "[your address]"


def redact_owner(raw: str, owner_email: str) -> str:
    """Replace the mailbox owner's own address before anything is analyzed or stored."""
    return re.sub(re.escape(owner_email), OWNER_PLACEHOLDER, raw, flags=re.IGNORECASE)


async def public(session, mb: Mailbox) -> dict:
    scanned = (await session.execute(select(func.count()).select_from(Analysis).where(
        Analysis.mailbox_id == mb.id))).scalar_one()
    flagged = (await session.execute(select(func.count()).select_from(Analysis).where(
        Analysis.mailbox_id == mb.id, Analysis.label.in_(("SCAM", "SUSPICIOUS"))))).scalar_one()
    return {"id": mb.id, "provider": mb.provider, "email": mb.email, "host": mb.host,
            "status": mb.status, "last_checked_at": iso(mb.last_checked_at),
            "last_error": mb.last_error, "created_at": iso(mb.created_at), "scanned": scanned,
            "flagged": flagged, "label_mode": mb.label_mode, "retention_days": mb.retention_days}


def _connect_blocking(host: str, port: int, user: str, password: str) -> tuple[int, int, bool]:
    conn = imap.open_session(host, port, user, password)
    try:
        uidvalidity, uidnext = imap.inbox_state(conn)
        return uidvalidity, uidnext, imap.is_gmail(conn)
    finally:
        imap.close(conn)


async def connect(owner_hash: str, payload: dict) -> dict:
    provider = imap.BY_ID.get(str(payload.get("provider", "")))
    if provider is None:
        raise HTTPException(422, "unknown provider")
    if not provider["supported"]:
        raise HTTPException(422, provider.get("reason", "provider not supported"))
    email = str(payload.get("email", "")).strip()
    password = str(payload.get("app_password", ""))
    if not _EMAIL.match(email):
        raise HTTPException(422, "enter a valid email address")
    if not 4 <= len(password) <= 256:
        raise HTTPException(422, "enter the app password")
    if provider["id"] in ("gmail", "yahoo", "icloud"):
        password = password.replace(" ", "")   # app passwords are shown in spaced groups
    host = provider["host"] or str(payload.get("host", "")).strip().lower()
    if not _HOST.match(host or ""):
        raise HTTPException(422, "enter the IMAP server name, e.g. imap.example.com")
    try:
        retention = int(payload.get("retention_days", 7))
    except (TypeError, ValueError):
        raise HTTPException(422, "retention_days must be a number") from None
    if retention not in (1, 7, 30):
        raise HTTPException(422, "retention_days must be 1, 7 or 30")
    async with session_scope() as s:
        count = (await s.execute(select(func.count()).select_from(Mailbox).where(
            Mailbox.owner_hash == owner_hash))).scalar_one()
        if count >= 5:
            raise HTTPException(409, "at most 5 mailboxes per browser")
    try:
        uidvalidity, uidnext, gmail = await asyncio.to_thread(
            _connect_blocking, host, imap.PORT, email, password)
    except imap.ImapError as e:
        raise HTTPException(400, str(e)) from None
    mb_id = svc.new_id("mb")
    async with session_scope() as s:
        mb = Mailbox(id=mb_id, owner_hash=owner_hash, provider=provider["id"], email=email,
                     host=host, port=imap.PORT, secret=crypto.encrypt(password, mb_id),
                     status="active", label_mode="gmail-labels" if gmail else "imap-flags",
                     uidvalidity=uidvalidity, last_uid=max(0, uidnext - 1),  # new mail only
                     last_checked_at=datetime.now(timezone.utc), retention_days=retention)
        s.add(mb)
        await s.flush()
        log.info("mailbox connected", extra={"mailbox_id": mb_id, "provider": provider["id"]})
        return await public(s, mb)


async def owned(session, mailbox_id: str, owner_hash: str) -> Mailbox:
    mb = await session.get(Mailbox, mailbox_id[:40])
    if mb is None or mb.owner_hash != owner_hash:
        raise HTTPException(404, "not found")
    return mb


def _poll_blocking(mb: dict, password: str, limit: int) -> dict:
    conn = imap.open_session(mb["host"], mb["port"], mb["email"], password)
    try:
        uidvalidity, uidnext = imap.inbox_state(conn)
        last_uid = mb["last_uid"]
        if mb["uidvalidity"] is not None and uidvalidity != mb["uidvalidity"]:
            last_uid = max(0, uidnext - 1)   # mailbox was rebuilt: restart at "now"
            return {"uidvalidity": uidvalidity, "last_uid": last_uid, "messages": []}
        msgs = imap.fetch_new(conn, last_uid, limit)
        return {"uidvalidity": uidvalidity,
                "last_uid": max([last_uid] + [u for u, _ in msgs]), "messages": msgs}
    finally:
        imap.close(conn)


async def poll(mailbox_id: str) -> int:
    """Fetch new mail for one mailbox and queue it. Returns the number queued."""
    s_ = get_settings()
    async with session_scope() as s:
        mb = await s.get(Mailbox, mailbox_id)
        if mb is None or mb.status == "paused":
            return 0
        snap = {"host": mb.host, "port": mb.port, "email": mb.email, "last_uid": mb.last_uid,
                "uidvalidity": mb.uidvalidity, "owner": mb.owner_hash}
        try:
            password = crypto.decrypt(mb.secret, mb.id)
        except Exception:  # noqa: BLE001
            mb.status, mb.last_error = "error", "stored credential could not be decrypted"
            return 0
    try:
        res = await asyncio.to_thread(_poll_blocking, snap, password, s_.mailbox_max_per_poll)
        error = None
    except imap.ImapError as e:
        res, error = None, str(e)
    except Exception as e:  # noqa: BLE001 - network blips
        res, error = None, f"temporary error: {type(e).__name__}"
    finally:
        password = ""   # noqa: F841 - drop the plaintext reference promptly
    queued = 0
    async with session_scope() as s:
        mb = await s.get(Mailbox, mailbox_id)
        if mb is None:
            return 0
        mb.last_checked_at = datetime.now(timezone.utc)
        if res is None:
            mb.status, mb.last_error = "error", error[:300]
            return 0
        mb.status, mb.last_error = ("active" if mb.status != "paused" else "paused"), None
        mb.uidvalidity, mb.last_uid = res["uidvalidity"], res["last_uid"]
        for uid, raw in res["messages"]:
            if not raw:
                continue
            text = redact_owner(raw.decode("utf-8", "replace"), snap["email"])
            ext = f"mbx:{mailbox_id}:{res['uidvalidity']}:{uid}"
            exists = (await s.execute(select(Analysis.id).where(
                Analysis.external_id == ext))).scalar_one_or_none()
            if exists:
                continue
            await svc.create(s, source="mailbox", raw=text, external_id=ext,
                             owner_hash=snap["owner"], mailbox_id=mailbox_id)
            queued += 1
    return queued


def _label_blocking(mb: dict, password: str, uid: int, label: str) -> None:
    conn = imap.open_session(mb["host"], mb["port"], mb["email"], password)
    try:
        imap.apply_label(conn, uid, label, mb["gmail"])
    finally:
        imap.close(conn)


async def label_verdict(analysis_id: str) -> None:
    """After a mailbox email is analyzed, tag it in the mailbox (SCAM / SUSPICIOUS only)."""
    async with session_scope() as s:
        a = await s.get(Analysis, analysis_id)
        if (a is None or not a.mailbox_id or a.labeled_at or a.status != "done"
                or a.label not in ("SCAM", "SUSPICIOUS") or not a.external_id):
            return
        mb = await s.get(Mailbox, a.mailbox_id)
        if mb is None or mb.status == "paused":
            return
        _, _, validity, uid = a.external_id.split(":")
        if mb.uidvalidity is not None and int(validity) != mb.uidvalidity:
            return  # UIDs no longer valid; never risk tagging the wrong message
        snap = {"host": mb.host, "port": mb.port, "email": mb.email,
                "gmail": mb.label_mode == "gmail-labels"}
        password = crypto.decrypt(mb.secret, mb.id)
        label = a.label
    try:
        await asyncio.to_thread(_label_blocking, snap, password, int(uid), label)
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
        await s.delete(mb)
    log.info("mailbox removed", extra={"mailbox_id": mailbox_id, "purged": purge})
