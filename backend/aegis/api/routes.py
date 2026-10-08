"""HTTP API v1. Contract: docs/API.md."""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import (FileResponse, JSONResponse, RedirectResponse,
                               StreamingResponse)
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from .. import __version__
from ..core.config import get_settings
from ..core.events import bus
from ..core.logging import get_logger
from ..core.security import limit_general, limit_submit, require_api_key
from ..core.viewer import require_viewer, viewer_hash
from ..db.models import Analysis, AuditEvent, Mailbox, RedteamRun, StageRun
from ..db.session import iso, session_scope
from ..providers import oauth
from ..providers.agentboxd import message_scores, message_to_raw, verify_signature
from ..services import abuse, campaigns, mailboxes, redteam
from ..services import analysis as svc
from ..services.samples import BY_ID as SAMPLES_BY_ID
from ..services.samples import SAMPLES

log = get_logger("api")

public = APIRouter(prefix="/api/v1", dependencies=[Depends(limit_general)])
private = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key),
                                                    Depends(limit_general)])


def _worker(request: Request):
    return request.app.state.worker


# --------------------------------------------------------------------------- public

@public.get("/health")
async def health(request: Request) -> dict:
    s = get_settings()
    return {"ok": True, "version": __version__, "llm": s.llm_configured,
            "agentboxd": s.agentboxd_configured,
            "vision": bool(s.vision_enabled and importlib.util.find_spec("playwright"))}


@public.get("/share/{token}")
async def share(token: str) -> dict:
    if not token.startswith("s_") or len(token) > 64:
        raise HTTPException(404, "not found")
    async with session_scope() as s:
        a = (await s.execute(select(Analysis).where(Analysis.share_token == token))
             ).scalar_one_or_none()
        if a is None or a.source == "redteam":
            raise HTTPException(404, "not found")
        return await svc.detail_of(s, a, public=True)


@public.post("/ingest/agentboxd", status_code=202)
async def ingest_agentboxd(request: Request) -> JSONResponse:
    s = get_settings()
    if not s.agentboxd_webhook_secret:
        raise HTTPException(503, "webhook ingestion is not configured")
    body = await request.body()   # bounded by BodyLimitMiddleware while streaming
    if not verify_signature(body, request.headers.get("x-mailroom-signature"),
                            s.agentboxd_webhook_secret):
        async with session_scope() as db:
            db.add(AuditEvent(event="webhook_bad_signature",
                              detail={"ip": request.client.host if request.client else "?"}))
        raise HTTPException(401, "bad webhook signature")
    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(400, "malformed JSON") from None
    if not isinstance(event, dict):
        raise HTTPException(400, "webhook body must be a JSON object")
    d = event.get("data", event)
    msg = d.get("message", d) if isinstance(d, dict) else {}
    msg = msg if isinstance(msg, dict) else {}
    message_id = str(msg.get("id") or (d.get("message_id") if isinstance(d, dict) else "")
                     or event.get("message_id") or "")[:128]
    if not message_id:
        raise HTTPException(400, "no message id in webhook")
    inbox_id = str(msg.get("inbox_id") or (d.get("inbox_id") if isinstance(d, dict) else "")
                   or s.agentboxd_inbox_id or "")[:128] or None
    has_content = bool(msg.get("text") or msg.get("extracted_text") or msg.get("html"))
    raw, html = message_to_raw(msg) if has_content else ("", "")
    try:
        async with session_scope() as db:
            a = await svc.create(db, source="webhook", raw=raw, raw_html=html,
                                 provider_scores=message_scores(msg), external_id=message_id,
                                 inbox_id=inbox_id, needs_fetch=not has_content)
            db.add(AuditEvent(event="webhook_accepted",
                              detail={"message_id": message_id, "analysis_id": a.id}))
            aid = a.id
    except IntegrityError:
        return JSONResponse({"ok": True, "duplicate": True}, status_code=200)
    _worker(request).notify()
    return JSONResponse({"ok": True, "id": aid}, status_code=202)


# --------------------------------------------------------------------------- private

@private.get("/config/public")
async def config_public() -> dict:
    s = get_settings()
    return {"inbox_address": s.agentboxd_inbox_address,
            "features": {"vision": s.vision_enabled, "inbox": s.agentboxd_configured,
                         "llm": s.llm_configured}}


def _mask_sender(sender: str | None) -> str | None:
    """`sh***@gmail.com`: enough for a tester to spot their own mail, never the full address
    or display name."""
    m = re.search(r"([\w.+-]+)@([\w-]+(?:\.[\w-]+)+)", sender or "")
    if not m:
        return None
    return f"{m.group(1)[:2]}***@{m.group(2).lower()}"


@private.get("/inbox/live")
async def inbox_live(limit: int = 20) -> dict:
    """Recent mail that arrived at the AgentBoxD inbox, with pipeline progress, for the
    live test page. Subject, sender and id are shown only for public inbox mail
    (INBOX_PUBLIC=true); private rows carry status and verdict only."""
    s = get_settings()
    if not s.agentboxd_configured:
        return {"enabled": False, "address": None, "public": False, "items": []}
    limit = max(1, min(limit, 50))
    async with session_scope() as session:
        rows = (await session.execute(
            select(Analysis)
            .where(Analysis.source.in_(("poller", "webhook")),
                   Analysis.inbox_id == s.agentboxd_inbox_id)
            .order_by(Analysis.created_at.desc(), Analysis.id.desc())
            .limit(limit))).scalars().all()
        stages: dict[str, list[dict]] = {}
        if rows:
            for st in (await session.execute(
                    select(StageRun).where(StageRun.analysis_id.in_([a.id for a in rows]))
                    .order_by(StageRun.seq))).scalars():
                stages.setdefault(st.analysis_id, []).append(
                    {"name": st.name, "status": st.status})
    items = []
    for a in rows:
        shown = a.visibility == "public"
        items.append({
            # opaque row key: stable across polls, not the capability id
            "key": hashlib.sha256(a.id.encode()).hexdigest()[:12],
            "id": a.id if shown else None,
            "created_at": iso(a.created_at), "status": a.status, "label": a.label,
            "score": a.score, "duration_s": a.duration_s,
            "subject": a.subject if shown else None,
            "sender": _mask_sender(a.sender) if shown else None,
            "replied": a.replied_at is not None, "private": not shown,
            "stages": stages.get(a.id, []),
        })
    return {"enabled": True, "address": s.agentboxd_inbox_address, "public": s.inbox_public,
            "items": items}


async def _read_submission(request: Request) -> tuple[str, str]:
    """(raw, source) from JSON {raw | sample_id} or a multipart .eml/.txt upload."""
    s = get_settings()
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("multipart/form-data"):
        form = await request.form()
        f = form.get("file")
        if f is None or isinstance(f, str):
            raise HTTPException(422, "multipart upload needs a 'file' field")
        data = await f.read(s.max_upload_bytes + 1)
        if len(data) > s.max_upload_bytes:
            raise HTTPException(413, "file too large")
        return data.decode("utf-8", "replace"), "web"
    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(400, "expected JSON or multipart") from None
    if not isinstance(payload, dict):
        raise HTTPException(422, "expected a JSON object")
    if payload.get("sample_id"):
        sample = SAMPLES_BY_ID.get(str(payload["sample_id"]))
        if sample is None:
            raise HTTPException(404, "unknown sample")
        return sample["raw"], "sample"
    raw = payload.get("raw")
    if not isinstance(raw, str):
        raise HTTPException(422, "'raw' must be a string")
    if len(raw.encode("utf-8", "replace")) > s.max_upload_bytes:
        raise HTTPException(413, "email too large")
    return raw, "web"


@private.post("/analyses", status_code=202, dependencies=[Depends(limit_submit)])
async def create_analysis(request: Request) -> JSONResponse:
    raw, source = await _read_submission(request)
    if len(raw.strip()) < 10:
        raise HTTPException(422, "paste the full email (at least a sentence)")
    async with session_scope() as s:
        a = await svc.create(s, source=source, raw=raw, owner_hash=viewer_hash(request))
        aid = a.id
    _worker(request).notify()
    return JSONResponse({"id": aid, "status": "queued"}, status_code=202)


@private.get("/analyses")
async def list_analyses(request: Request, limit: int = 50, cursor: str | None = None,
                        label: str | None = None, q: str | None = None,
                        source: str | None = None, mine: bool = False) -> dict:
    limit = max(1, min(limit, 100))
    viewer = viewer_hash(request)
    async with session_scope() as s:
        stmt = select(Analysis)
        if mine:
            stmt = stmt.where(Analysis.owner_hash == (viewer or "-"))
        elif viewer:
            stmt = stmt.where(or_(Analysis.visibility == "public", Analysis.owner_hash == viewer))
        else:
            stmt = stmt.where(Analysis.visibility == "public")
        if source:
            stmt = stmt.where(Analysis.source == source)
        else:
            stmt = stmt.where(Analysis.source != "redteam")
        if label:
            if label not in svc.LABELS:
                raise HTTPException(422, "unknown label")
            stmt = stmt.where(Analysis.label == label)
        if q:
            like = f"%{q[:100]}%"
            stmt = stmt.where(or_(Analysis.subject.ilike(like), Analysis.sender.ilike(like)))
        if cursor:
            c = await s.get(Analysis, cursor)
            if c is not None:
                stmt = stmt.where(or_(Analysis.created_at < c.created_at,
                                      (Analysis.created_at == c.created_at)
                                      & (Analysis.id < c.id)))
        rows = (await s.execute(stmt.order_by(Analysis.created_at.desc(), Analysis.id.desc())
                                .limit(limit + 1))).scalars().all()
        items = [svc.summary_of(a, viewer) for a in rows[:limit]]
        return {"items": items, "next_cursor": rows[limit - 1].id if len(rows) > limit else None}


async def _get(s, analysis_id: str) -> Analysis:
    if len(analysis_id) > 40:
        raise HTTPException(404, "not found")
    a = await s.get(Analysis, analysis_id)
    if a is None:
        raise HTTPException(404, "not found")
    return a


@private.get("/analyses/{analysis_id}")
async def get_analysis(analysis_id: str, request: Request) -> dict:
    async with session_scope() as s:
        return await svc.detail_of(s, await _get(s, analysis_id), viewer=viewer_hash(request))


@private.get("/analyses/{analysis_id}/screenshot")
async def screenshot(analysis_id: str) -> FileResponse:
    async with session_scope() as s:
        await _get(s, analysis_id)
    path = svc.screenshot_path(get_settings(), analysis_id)
    if not os.path.exists(path):
        raise HTTPException(404, "no screenshot")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private"})


@private.get("/analyses/{analysis_id}/abuse-report")
async def abuse_report(analysis_id: str) -> dict:
    async with session_scope() as s:
        a = await _get(s, analysis_id)
        if a.status != "done":
            raise HTTPException(409, "analysis not finished")
        return {"markdown": abuse.build(await svc.detail_of(s, a))}


def _sse(event: str, data: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()


@private.get("/analyses/{analysis_id}/events")
async def events(analysis_id: str, request: Request) -> StreamingResponse:
    async with session_scope() as s:
        await _get(s, analysis_id)

    async def stream():
        q = bus.subscribe(analysis_id)   # subscribe first so nothing slips between
        try:
            async with session_scope() as s:
                a = await s.get(Analysis, analysis_id)
                stages = await svc.stages_of(s, analysis_id)
                status, label, score, error = a.status, a.label, a.score, a.error
            for st in stages:
                if st["status"] != "pending":
                    yield _sse("stage", {k: v for k, v in st.items() if v is not None})
            if status in ("done", "failed"):
                yield _sse("done", {"id": analysis_id, "status": status, "label": label,
                                    "score": score, "error": error})
                return
            yield _sse("status", {"status": status})
            while True:
                if await request.is_disconnected():
                    return
                try:
                    event, data = await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield b": ping\n\n"
                    continue
                yield _sse(event, data)
                if event == "done":
                    return
        finally:
            bus.unsubscribe(analysis_id, q)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@private.get("/stats")
async def stats() -> dict:
    async with session_scope() as s:
        base = select(Analysis).where(Analysis.source != "redteam", Analysis.status == "done")
        rows = (await s.execute(base)).scalars().all()
        by_label = {lbl: 0 for lbl in svc.LABELS}
        techniques: dict[str, int] = {}
        brands: dict[str, int] = {}
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        last_24h, durations = 0, []
        for a in rows:
            by_label[a.label] = by_label.get(a.label, 0) + 1
            if a.duration_s:
                durations.append(a.duration_s)
            created = a.created_at if a.created_at.tzinfo else a.created_at.replace(
                tzinfo=timezone.utc)
            last_24h += created >= since
            for t in (a.result or {}).get("techniques", []):
                techniques[t] = techniques.get(t, 0) + 1
            if a.label != "LIKELY_SAFE":
                for b in ((a.result or {}).get("triage") or {}).get("brand_mentions", []):
                    brands[b] = brands.get(b, 0) + 1
        n_campaigns = len((await campaigns.campaigns(s))["campaigns"])
    top = lambda d: [{"name": k, "count": v}  # noqa: E731
                     for k, v in sorted(d.items(), key=lambda kv: -kv[1])[:6]]
    return {"total": len(rows), "by_label": by_label, "last_24h": last_24h,
            "avg_duration_s": round(sum(durations) / len(durations), 1) if durations else 0,
            "top_techniques": top(techniques), "top_brands": top(brands),
            "campaigns": n_campaigns}


@private.get("/campaigns")
async def get_campaigns(request: Request) -> dict:
    async with session_scope() as s:
        return await campaigns.campaigns(s, viewer=viewer_hash(request))


@private.get("/samples")
async def samples() -> list[dict]:
    return SAMPLES


@private.post("/redteam/runs", status_code=202, dependencies=[Depends(limit_submit)])
async def create_redteam_run(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(400, "expected JSON") from None
    if not isinstance(payload, dict):
        raise HTTPException(422, "expected a JSON object")
    if payload.get("sample_id"):
        sample = SAMPLES_BY_ID.get(str(payload["sample_id"]))
        if sample is None:
            raise HTTPException(404, "unknown sample")
        raw = sample["raw"]
    elif isinstance(payload.get("raw"), str) and len(payload["raw"].strip()) >= 10:
        raw = payload["raw"][: get_settings().max_upload_bytes]
    else:
        raise HTTPException(422, "provide sample_id or raw")
    try:
        n = max(1, min(int(payload.get("n", 5)), 8))
        seed = int(payload.get("seed") or secrets.randbelow(10**9))
    except (TypeError, ValueError):
        raise HTTPException(422, "n and seed must be integers") from None
    async with session_scope() as s:
        run = await redteam.create_run(s, raw, n, seed)
        if not run.variants:
            raise HTTPException(422, "no mutation applies to this email (needs a link or brand)")
        rid = run.id
    _worker(request).notify()
    return JSONResponse({"id": rid}, status_code=202)


@private.get("/redteam/runs")
async def list_redteam_runs() -> list[dict]:
    async with session_scope() as s:
        runs = (await s.execute(select(RedteamRun).order_by(RedteamRun.created_at.desc())
                                .limit(20))).scalars().all()
        out = []
        for r in runs:
            d = await redteam.run_detail(s, r)
            out.append({"id": d["id"], "created_at": d["created_at"], "status": d["status"],
                        "base_subject": d["base_subject"], "summary": d["summary"]})
        return out


@private.get("/redteam/runs/{run_id}")
async def get_redteam_run(run_id: str) -> dict:
    async with session_scope() as s:
        r = await s.get(RedteamRun, run_id[:40])
        if r is None:
            raise HTTPException(404, "not found")
        return await redteam.run_detail(s, r)


@private.get("/redteam/summary")
async def redteam_summary() -> dict:
    async with session_scope() as s:
        return await redteam.summary(s)


# --------------------------------------------------------------------------- mailboxes

@private.get("/mailbox-providers")
async def mailbox_providers() -> list[dict]:
    return mailboxes.provider_list()


@private.post("/oauth/{provider}/start", dependencies=[Depends(limit_submit)])
async def oauth_start(provider: str, request: Request) -> dict:
    owner = require_viewer(request)
    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = {}
    retention = payload.get("retention_days", 7) if isinstance(payload, dict) else 7
    return mailboxes.sign_in_start(provider, owner, retention)


@private.get("/oauth/status")
async def oauth_status(request: Request, state: str = "") -> dict:
    return mailboxes.sign_in_status(state[:128], require_viewer(request))


@private.get("/oauth/{provider}/callback")
async def oauth_callback(provider: str, request: Request, code: str = "", state: str = "",
                         error: str = "") -> RedirectResponse:
    """The provider sends the browser here. Always ends with a redirect: to /inbox
    when this browser started the sign-in, else to the confirmation page."""
    from urllib.parse import quote

    def back(query: str) -> RedirectResponse:
        return RedirectResponse(f"/inbox?{query}", status_code=303)

    state = state[:128]
    if error or not code:
        try:
            p = oauth.get_pending(state)
            if p["status"] == "pending":
                p["status"], p["error"] = "error", "Sign-in was cancelled."
        except oauth.OAuthError:
            pass
        return back("signin_error=" + quote("Sign-in was cancelled." if error else
                                            "Sign-in failed. Please try again."))
    try:
        outcome = await mailboxes.sign_in_callback(provider, viewer_hash(request),
                                                   code[:4096], state)
    except oauth.OAuthError as e:
        return back("signin_error=" + quote(str(e)))
    except HTTPException as e:
        return back("signin_error=" + quote(str(e.detail)))
    except Exception:  # noqa: BLE001 - network failures talking to the provider
        log.exception("sign-in failed", extra={"provider": provider[:16]})
        return back("signin_error=" + quote("Could not reach the sign-in service. Please try "
                                            "again."))
    if outcome == "confirm":
        return RedirectResponse(f"/connect?state={quote(state)}", status_code=303)
    request.app.state.mailbox_poller.trigger(mailboxes.mailbox_of(state))
    return back("signin=connected")


@private.get("/oauth/pairing")
async def oauth_pairing(state: str = "") -> dict:
    try:
        return mailboxes.sign_in_pairing(state[:128])
    except oauth.OAuthError as e:
        raise HTTPException(404, str(e)) from None


@private.post("/oauth/confirm", dependencies=[Depends(limit_submit)])
async def oauth_confirm(request: Request) -> dict:
    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(400, "expected JSON") from None
    if not isinstance(payload, dict):
        raise HTTPException(422, "expected a JSON object")
    try:
        mb = await mailboxes.sign_in_confirm(str(payload.get("state", ""))[:128],
                                             payload.get("connect") is True)
    except oauth.OAuthError as e:
        raise HTTPException(404, str(e)) from None
    if mb is None:
        return {"status": "cancelled"}
    request.app.state.mailbox_poller.trigger(mb["id"])
    return {"status": "connected", "email": mb["email"]}


@private.get("/mailboxes")
async def list_mailboxes(request: Request) -> list[dict]:
    owner = viewer_hash(request)
    if owner is None:
        return []
    async with session_scope() as s:
        rows = (await s.execute(select(Mailbox).where(Mailbox.owner_hash == owner)
                                .order_by(Mailbox.created_at))).scalars().all()
        return [await mailboxes.public(s, m) for m in rows]


@private.post("/mailboxes/{mailbox_id}/check", status_code=202)
async def check_mailbox(mailbox_id: str, request: Request) -> dict:
    owner = require_viewer(request)
    async with session_scope() as s:
        await mailboxes.owned(s, mailbox_id, owner)
    request.app.state.mailbox_poller.trigger(mailbox_id)
    return {"ok": True}


async def _set_status(mailbox_id: str, request: Request, status: str) -> dict:
    owner = require_viewer(request)
    async with session_scope() as s:
        mb = await mailboxes.owned(s, mailbox_id, owner)
        mb.status, mb.last_error = status, None
        await s.flush()
        return await mailboxes.public(s, mb)


@private.post("/mailboxes/{mailbox_id}/pause")
async def pause_mailbox(mailbox_id: str, request: Request) -> dict:
    return await _set_status(mailbox_id, request, "paused")


@private.post("/mailboxes/{mailbox_id}/resume")
async def resume_mailbox(mailbox_id: str, request: Request) -> dict:
    out = await _set_status(mailbox_id, request, "active")
    request.app.state.mailbox_poller.trigger(mailbox_id)
    return out


@private.delete("/mailboxes/{mailbox_id}", status_code=204)
async def delete_mailbox(mailbox_id: str, request: Request, purge: bool = False):
    from fastapi import Response
    await mailboxes.remove(mailbox_id, require_viewer(request), purge)
    return Response(status_code=204)
