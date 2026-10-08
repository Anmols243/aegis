"""Live test inbox feed (/live): mail that reached the AgentBoxD inbox, partially censored.

The test inbox is a demo, so every visitor sees each email's subject, a masked sender,
a short preview and the full dissection. Personal details are censored on the server:
addresses keep two characters of the local part, display names keep initials, long
digit runs (phones, account numbers) keep the last two digits, and long tokens (codes,
keys) keep four characters. Links and domains stay: they are the evidence. The analysis
id (the capability that opens the uncensored case) is shared only for public inbox mail.
"""
from __future__ import annotations

import hashlib
import re

from sqlalchemy import select

from ..core.config import Settings
from ..db.models import Analysis, StageRun
from ..db.session import iso
from . import analysis as svc

INBOX_SOURCES = ("poller", "webhook")

_EMAIL = re.compile(r"([\w.+-]+)@([\w-]+(?:\.[\w-]+)+)")
_NAME_BEFORE_ADDR = re.compile(r"(?P<name>[^<>,\n\"]{1,80}?)\s*<(?=[^<>\s]+@)")
_DIGITS = re.compile(r"(?<![\w/.])\+?\d[\d\s().-]{4,}\d(?![\w/])")
_TOKEN = re.compile(r"\b[A-Za-z0-9_-]{24,}\b")
# keys whose values are identifiers, enums, timestamps or numbers: never censored
_KEEP = {"id", "key", "status", "label", "name", "kind", "severity", "source", "visibility",
         "artifact", "strength", "technique", "state", "verdict", "kind_label"}


def row_key(analysis_id: str) -> str:
    """Opaque, stable row key: not the capability id."""
    return hashlib.sha256(analysis_id.encode()).hexdigest()[:12]


def mask_sender(sender: str | None) -> str | None:
    """`sh***@gmail.com`: enough for a tester to spot their own mail, never the full
    address or display name."""
    m = _EMAIL.search(sender or "")
    if not m:
        return None
    return f"{m.group(1)[:2]}***@{m.group(2).lower()}"


def censor(text: str) -> str:
    """Partially censor personal details in free text (see module docstring)."""
    if not text:
        return text

    def name(m: re.Match) -> str:
        words = m.group("name").strip().strip('"').split()
        return " ".join(f"{w[0]}***" for w in words if w) + " <"

    text = _NAME_BEFORE_ADDR.sub(name, text)
    text = _EMAIL.sub(lambda m: f"{m.group(1)[:2]}***@{m.group(2)}", text)
    text = _DIGITS.sub(lambda m: "***" + re.sub(r"\D", "", m.group(0))[-2:], text)
    return _TOKEN.sub(lambda m: m.group(0)[:4] + "***", text)


def censor_tree(value, key: str = ""):
    """Censor every free-text string in a JSON-like structure."""
    if isinstance(value, dict):
        return {k: censor_tree(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [censor_tree(v, key) for v in value]
    if isinstance(value, str) and key not in _KEEP and not key.endswith("_at"):
        return censor(value)
    return value


def _preview(a: Analysis, n: int = 160) -> str:
    text = ((a.result or {}).get("email") or {}).get("text") or ""
    text = re.sub(r"\s+", " ", text).strip()
    return censor(text[:n * 2])[:n]


async def recent(session, settings: Settings, limit: int) -> list[Analysis]:
    return list((await session.execute(
        select(Analysis)
        .where(Analysis.source.in_(INBOX_SOURCES),
               Analysis.inbox_id == settings.agentboxd_inbox_id)
        .order_by(Analysis.created_at.desc(), Analysis.id.desc())
        .limit(limit))).scalars().all())


async def feed(session, settings: Settings, limit: int) -> list[dict]:
    rows = await recent(session, settings, limit)
    stages: dict[str, list[dict]] = {}
    if rows:
        for st in (await session.execute(
                select(StageRun).where(StageRun.analysis_id.in_([a.id for a in rows]))
                .order_by(StageRun.seq))).scalars():
            stages.setdefault(st.analysis_id, []).append({"name": st.name, "status": st.status})
    return [{
        "key": row_key(a.id),
        "id": a.id if a.visibility == "public" else None,
        "created_at": iso(a.created_at), "status": a.status, "label": a.label,
        "score": a.score, "duration_s": a.duration_s,
        "subject": censor(a.subject or "") or None,
        "sender": mask_sender(a.sender),
        "preview": _preview(a),
        "replied": a.replied_at is not None,
        "private": a.visibility != "public",
        "stages": stages.get(a.id, []),
    } for a in rows]


async def detail(session, settings: Settings, key: str) -> dict | None:
    """The censored dissection of one inbox email, found by its row key."""
    for a in await recent(session, settings, 50):
        if row_key(a.id) != key:
            continue
        out = await svc.detail_of(session, a, public=True)
        text = ((a.result or {}).get("email") or {}).get("text") or ""
        out["email"]["text"] = text[:4000]
        out["sender"] = mask_sender(a.sender)
        out = censor_tree(out)
        out["id"], out["key"] = None, key
        out["share_token"] = None
        return out
    return None
