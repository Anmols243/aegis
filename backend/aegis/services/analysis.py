"""Analysis lifecycle: create -> (worker) process -> serialize."""
from __future__ import annotations

import os
import secrets
import time
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import select, update

from ..core.config import Settings, get_settings
from ..core.events import bus
from ..core.logging import get_logger
from ..db.models import Analysis, StageRun
from ..db.session import iso, session_scope
from ..pipeline.context import PipelineContext
from ..pipeline.parse import parse_email
from ..pipeline.runner import STAGE_NAMES, run_pipeline
from ..providers.agentboxd import AgentBoxD, message_scores, message_to_raw
from ..providers.llm import LLMClient
from . import campaigns, claims

log = get_logger("analysis")

LABELS = ("SCAM", "SUSPICIOUS", "LIKELY_SAFE")


PUBLIC_SOURCES = ("sample", "redteam")


def new_id(prefix: str = "a") -> str:
    # time-ordered prefix keeps ids sortable; the 64-bit random tail makes a private
    # analysis id an unguessable capability (it is the only way to open one)
    return f"{prefix}_{int(time.time() * 1000):x}{secrets.token_hex(8)}"


def default_visibility(source: str, settings: Settings | None = None) -> str:
    if source in PUBLIC_SOURCES:
        return "public"
    if source in ("webhook", "poller") and (settings or get_settings()).inbox_public:
        return "public"
    return "private"


def _display_subject(source: str, subject: str) -> str:
    """Test-inbox subjects lose the routing code (services/claims.py) for display."""
    return claims.strip_code(subject) if source in ("webhook", "poller") else (subject or "")


async def create(session, *, source: str, raw: str, raw_html: str = "",
                 provider_scores: dict | None = None, external_id: str | None = None,
                 inbox_id: str | None = None, needs_fetch: bool = False,
                 owner_hash: str | None = None, mailbox_id: str | None = None) -> Analysis:
    preview = parse_email(raw, raw_html) if raw or raw_html else None
    if owner_hash is None and source in ("webhook", "poller") and preview:
        # test-inbox mail belongs to the browser whose code it carries, or whose code its
        # sender used before (services/claims.py)
        owner_hash = await claims.resolve(session, preview.subject, preview.text, preview.sender)
    a = Analysis(id=new_id(), source=source, status="queued", raw=raw or "",
                 raw_html=raw_html or "", provider_scores=provider_scores or {},
                 external_id=external_id, inbox_id=inbox_id, needs_fetch=int(needs_fetch),
                 subject=_display_subject(source, preview.subject if preview else "")[:300],
                 sender=(preview.sender if preview else "")[:300],
                 share_token="s_" + secrets.token_urlsafe(16), result={},
                 visibility=default_visibility(source), owner_hash=owner_hash,
                 mailbox_id=mailbox_id)
    session.add(a)
    for i, name in enumerate(STAGE_NAMES):
        session.add(StageRun(analysis_id=a.id, name=name, seq=i, status="pending"))
    await session.flush()
    return a


def _stage_reporter(analysis_id: str):
    async def on_stage(name: str, status: str, **fields) -> None:
        values = {"status": status}
        for k in ("started_at", "duration_s", "summary", "error"):
            if k in fields and fields[k] is not None:
                values[k] = fields[k]
        async with session_scope() as s:
            await s.execute(update(StageRun).where(StageRun.analysis_id == analysis_id,
                                                   StageRun.name == name).values(**values))
        event = {"name": name, "status": status}
        if fields.get("started_at"):
            event["started_at"] = iso(fields["started_at"])
        for k in ("duration_s", "summary", "error"):
            if fields.get(k) is not None:
                event[k] = fields[k]
        bus.publish(analysis_id, "stage", event)
    return on_stage


def _assemble(ctx: PipelineContext) -> dict:
    r = ctx.results
    verdict = r["arbiter"]
    rep = r["report"]
    forensic, signals, triage = r.get("forensic"), r.get("signals"), r.get("triage")
    vision, sandbox, graph = r.get("vision"), r.get("sandbox"), r.get("graph") or {}
    return {
        "summary": rep["summary"],
        "email": ctx.email.public(),
        "verdict": verdict.public(),
        "red_flags": rep["red_flags"],
        "findings": [asdict(f) for f in forensic.findings] if forensic else [],
        "signals": [asdict(s) for s in signals.signals] if signals else [],
        "techniques": forensic.techniques if forensic else [],
        "triage": asdict(triage) if triage else None,
        "vision": ({"impersonated_brand": vision.impersonated_brand,
                    "confidence": vision.confidence, "notable_regions": vision.notable_regions,
                    "reason": vision.reason, "has_screenshot": bool(vision.screenshot)}
                   if vision else None),
        "sandbox": [v.public() for v in sandbox] if sandbox else [],
        "campaign": {"campaign_id": None, "note": graph.get("note", ""),
                     "related": graph.get("related", [])},
        "actions": rep["actions"],
        "card_markdown": rep["card_markdown"],
    }


async def process(analysis_id: str, settings: Settings, llm: LLMClient,
                  agentboxd: AgentBoxD) -> None:
    """Run the pipeline for one claimed analysis. Raises on failure (worker retries)."""
    async with session_scope() as s:
        a = await s.get(Analysis, analysis_id)
        if a is None:
            return
        source, raw, raw_html = a.source, a.raw, a.raw_html
        scores, needs_fetch, external_id = dict(a.provider_scores or {}), a.needs_fetch, a.external_id
    if needs_fetch and external_id:
        msg = await agentboxd.get_message(external_id)
        raw, raw_html = message_to_raw(msg)
        scores = message_scores(msg) or scores
        async with session_scope() as s:
            values = {"raw": raw, "raw_html": raw_html, "provider_scores": scores, "needs_fetch": 0}
            row = await s.get(Analysis, analysis_id)
            if row is not None and row.owner_hash is None:
                p = parse_email(raw, raw_html)
                owner = await claims.resolve(s, p.subject, p.text, p.sender)
                if owner:
                    values["owner_hash"] = owner
            await s.execute(update(Analysis).where(Analysis.id == analysis_id).values(**values))

    started = time.monotonic()
    bus.publish(analysis_id, "status", {"status": "running"})
    ctx = PipelineContext(analysis_id=analysis_id, source=source, raw=raw, raw_html=raw_html,
                          provider_scores=scores, settings=settings, llm=llm)
    async with session_scope() as s:  # a retry starts from a clean slate
        await s.execute(update(StageRun).where(StageRun.analysis_id == analysis_id).values(
            status="pending", started_at=None, duration_s=None, summary="", error=None))
    await run_pipeline(ctx, _stage_reporter(analysis_id))
    result = _assemble(ctx)
    verdict = ctx.results["arbiter"]
    async with session_scope() as s:
        a = await s.get(Analysis, analysis_id)
        a.status, a.error = "done", None
        a.label, a.score, a.confidence = verdict.label, verdict.score, verdict.confidence
        a.subject = (_display_subject(source, ctx.email.subject) or a.subject)[:300]
        a.sender = (ctx.email.sender or a.sender)[:300]
        a.duration_s = round(time.monotonic() - started, 2)
        a.result = result
        await s.flush()
        if source != "redteam":
            result = dict(result)
            result["campaign"] = dict(result["campaign"],
                                      campaign_id=await campaigns.campaign_id_for(s, analysis_id))
            a.result = result
    log.info("analysis done", extra={"analysis_id": analysis_id, "label": verdict.label,
                                     "score": verdict.score, "source": source})
    bus.publish(analysis_id, "done", {"id": analysis_id, "status": "done",
                                      "label": verdict.label, "score": verdict.score})


async def maybe_reply(analysis_id: str, settings: Settings, agentboxd: AgentBoxD) -> None:
    """Reply in-thread with the verdict card for mail that came from the inbox."""
    if not (settings.agentboxd_auto_reply and agentboxd.configured):
        return
    async with session_scope() as s:
        a = await s.get(Analysis, analysis_id)
        if (a is None or a.source not in ("webhook", "poller") or a.replied_at
                or not a.external_id or a.status != "done"):
            return
        inbox, mid, card = a.inbox_id or settings.agentboxd_inbox_id, a.external_id, \
            a.result.get("card_markdown", "")
    try:
        await agentboxd.reply(inbox, mid, card)
    except Exception as e:  # noqa: BLE001 - reply failure must not fail the analysis
        log.warning("reply failed", extra={"analysis_id": analysis_id, "error": str(e)[:200]})
        return
    async with session_scope() as s:
        await s.execute(update(Analysis).where(Analysis.id == analysis_id)
                        .values(replied_at=datetime.now(timezone.utc)))


# --------------------------------------------------------------------------- serialization

def visible_to(a: Analysis, viewer: str | None) -> bool:
    """Listed for this viewer: public, or the viewer's own private analysis."""
    return a.visibility == "public" or (viewer is not None and a.owner_hash == viewer)


def summary_of(a: Analysis, viewer: str | None = None) -> dict:
    return {"id": a.id, "created_at": iso(a.created_at), "source": a.source, "status": a.status,
            "subject": a.subject, "sender": a.sender, "label": a.label, "score": a.score,
            "confidence": a.confidence, "duration_s": a.duration_s,
            "visibility": a.visibility or "private",
            "mine": viewer is not None and a.owner_hash == viewer,
            "mailbox_id": a.mailbox_id if viewer is not None and a.owner_hash == viewer else None,
            "purged": a.purged_at is not None}


async def _redact_related(session, related: list[dict], viewer: str | None) -> list[dict]:
    """Related emails the viewer may not list are shown only as 'a private email
    shares this infrastructure' (strength + kinds), never id, subject or values."""
    ids = [r.get("analysis_id") for r in related if r.get("analysis_id")]
    rows = {a.id: a for a in (await session.execute(
        select(Analysis).where(Analysis.id.in_(ids)))).scalars()} if ids else {}
    out = []
    for r in related:
        a = rows.get(r.get("analysis_id"))
        if a is not None and visible_to(a, viewer):
            out.append({**r, "subject": a.subject, "label": a.label, "private": False})
        elif a is not None:
            out.append({"private": True, "strength": r.get("strength"), "why": r.get("why")})
    return out


async def stages_of(session, analysis_id: str) -> list[dict]:
    rows = (await session.execute(select(StageRun).where(StageRun.analysis_id == analysis_id)
                                  .order_by(StageRun.seq))).scalars()
    return [{"name": r.name, "status": r.status, "started_at": iso(r.started_at),
             "duration_s": r.duration_s, "summary": r.summary, "error": r.error} for r in rows]


def screenshot_path(settings: Settings, analysis_id: str) -> str:
    return os.path.join(settings.data_dir, "screenshots", f"{analysis_id}.png")


async def detail_of(session, a: Analysis, public: bool = False,
                    viewer: str | None = None) -> dict:
    r = dict(a.result or {})
    out = summary_of(a, None if public else viewer)
    vision = r.get("vision")
    if vision is not None:
        vision = dict(vision)
        has = vision.pop("has_screenshot", False)
        vision["screenshot_url"] = f"/api/v1/analyses/{a.id}/screenshot" if has and not public \
            else None
    email = r.get("email") or parse_email(a.raw, a.raw_html).public()
    out.update({
        "error": a.error, "summary": r.get("summary", ""), "email": dict(email),
        "verdict": r.get("verdict"), "red_flags": r.get("red_flags", []),
        "findings": r.get("findings", []), "signals": r.get("signals", []),
        "techniques": r.get("techniques", []), "triage": r.get("triage"), "vision": vision,
        "sandbox": r.get("sandbox", []),
        "campaign": r.get("campaign") or {"campaign_id": None, "note": "", "related": []},
        "actions": r.get("actions", []), "stages": await stages_of(session, a.id),
        "share_token": a.share_token, "card_markdown": r.get("card_markdown", ""),
    })
    camp = dict(out["campaign"])
    camp["related"] = await _redact_related(session, camp.get("related") or [],
                                            None if public else viewer)
    out["campaign"] = camp
    if public:
        out["email"].pop("text", None)
        out["triage"] = None
        out["card_markdown"] = ""
        out["share_token"] = None
        out["campaign"] = {"campaign_id": None, "note": out["campaign"].get("note", ""),
                           "related": []}
    return out


# --------------------------------------------------------------------------- retention

def purge_row(a: Analysis, settings: Settings) -> None:
    """Delete the email content of a private analysis; keep the verdict.

    Kept: subject, sender, label, score, techniques, next steps, stage timings.
    Removed: raw message, HTML, body text, quoted evidence, extracted entities,
    link details, the AI summary, the reply card, and the screenshot."""
    r = dict(a.result or {})
    if r.get("email"):
        r["email"] = {**r["email"], "text": "", "html_available": False}
    r["findings"] = [{**f, "excerpt": ""} for f in r.get("findings", [])]
    r["signals"] = [{**s, "evidence": ""} for s in r.get("signals", [])]
    r["red_flags"] = [{**f, "evidence": ""} for f in r.get("red_flags", [])]
    r["sandbox"] = []
    r["triage"] = None
    r["summary"] = ""
    r["card_markdown"] = ""
    if r.get("vision"):
        r["vision"] = {**r["vision"], "has_screenshot": False}
    a.result, a.raw, a.raw_html = r, "", ""
    a.purged_at = datetime.now(timezone.utc)
    path = screenshot_path(settings, a.id)
    if os.path.exists(path):
        os.remove(path)


async def unpublish_inbox_mail() -> int:
    """Test-inbox mail made public while INBOX_PUBLIC was on goes back to private once it is
    off: otherwise a tester's own address stays on everyone's campaign graph. Returns how many."""
    async with session_scope() as s:
        res = await s.execute(update(Analysis).where(
            Analysis.source.in_(("webhook", "poller")), Analysis.visibility == "public",
        ).values(visibility="private"))
        return res.rowcount or 0


async def delete_owned(owner_hash: str) -> int:
    """Erase every analysis this browser owns (rows, stage runs, entities, screenshots) and
    forget which sender addresses route to it. Returns how many analyses were deleted."""
    from sqlalchemy import delete as sa_delete

    from ..db.models import Entity, SenderLink
    s_ = get_settings()
    async with session_scope() as s:
        await s.execute(sa_delete(SenderLink).where(SenderLink.owner_hash == owner_hash))
        ids = list((await s.execute(select(Analysis.id).where(
            Analysis.owner_hash == owner_hash))).scalars())
        if ids:
            await s.execute(sa_delete(Entity).where(Entity.analysis_id.in_(ids)))
            await s.execute(sa_delete(StageRun).where(StageRun.analysis_id.in_(ids)))
            await s.execute(sa_delete(Analysis).where(Analysis.id.in_(ids)))
    for aid in ids:
        path = screenshot_path(s_, aid)
        if os.path.exists(path):
            os.remove(path)
    return len(ids)


async def purge_expired(now: datetime | None = None) -> int:
    """Apply retention to private analyses. Returns how many were purged."""
    from datetime import timedelta

    from sqlalchemy import delete as sa_delete

    from ..db.models import Entity, Mailbox
    s_ = get_settings()
    now = now or datetime.now(timezone.utc)
    purged = 0
    async with session_scope() as s:
        retention = {m.id: m.retention_days for m in (await s.execute(select(Mailbox))).scalars()}
        rows = (await s.execute(select(Analysis).where(
            Analysis.visibility == "private", Analysis.purged_at.is_(None),
            Analysis.status.in_(("done", "failed"))))).scalars().all()
        for a in rows:
            days = retention.get(a.mailbox_id, s_.private_retention_days)
            created = a.created_at if a.created_at.tzinfo else a.created_at.replace(
                tzinfo=timezone.utc)
            if created > now - timedelta(days=days):
                continue
            purge_row(a, s_)
            if a.label not in ("SCAM", "SUSPICIOUS"):
                # legitimate mail: its addresses and links are personal, not threat intel
                await s.execute(sa_delete(Entity).where(Entity.analysis_id == a.id))
            purged += 1
    return purged
