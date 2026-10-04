"""Dashboard verdict store: SQLite record of every analyzed email.

Written by the webhook receiver after each analysis (and by demo scripts);
read by the dashboard API. `data/*.db` is gitignored runtime state.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone

# Set AEGIS_DASHBOARD_REDACT=1 when the dashboard might be seen by people
# who shouldn't read raw email contents (shared screen, public demo).
# Masks email addresses and phone-like numbers in sender/preview fields.
REDACT_PII = os.environ.get("AEGIS_DASHBOARD_REDACT") == "1"


def redact_pii(text: str) -> str:
    """Mask addresses and phone numbers. Best-effort, not a guarantee."""
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[email]", text)
    text = re.sub(r"\+?[\d][\d\s\-().]{6,}\d", "[phone]", text)
    return text


def _maybe_redact(sender: str, preview: str) -> tuple[str, str]:
    if REDACT_PII:
        return redact_pii(sender), redact_pii(preview)
    return sender, preview

SCHEMA = """
CREATE TABLE IF NOT EXISTS verdicts (
    email_id     TEXT PRIMARY KEY,
    received_at  TEXT NOT NULL,
    sender       TEXT DEFAULT '',
    label        TEXT DEFAULT '',
    confidence   REAL DEFAULT 0,
    score        REAL DEFAULT 0,
    contributions TEXT DEFAULT '{}',
    dissent      TEXT DEFAULT '[]',
    red_flags    TEXT DEFAULT '[]',
    campaign_note TEXT DEFAULT '',
    signals      TEXT DEFAULT '{}',
    body_preview TEXT DEFAULT '',
    det_signals  TEXT DEFAULT '[]',
    timings      TEXT DEFAULT '{}'
);
"""

# Migrations for DBs created before a column existed.
_MIGRATIONS = [
    "ALTER TABLE verdicts ADD COLUMN det_signals TEXT DEFAULT '[]'",
    "ALTER TABLE verdicts ADD COLUMN timings TEXT DEFAULT '{}'",
]


def _connect(path: str = "data/dashboard.db") -> sqlite3.Connection:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    for stmt in _MIGRATIONS:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass  # column already exists
    return conn


def record(res, body: str = "", path: str = "data/dashboard.db") -> None:
    """Persist an AnalysisResult. Duck-typed: no import of orchestrator."""
    v = res.verdict
    triage = res.triage
    forensic = res.forensic
    sandbox = res.sandbox or []
    flags = []
    if forensic:
        flags = [{"title": f.claim, "evidence": f.evidence.excerpt,
                  "severity": f.severity}
                 for f in forensic.findings if f.severity == "high"][:8]
    signals = {
        "forensic": round(forensic.risk_score, 3) if forensic else None,
        "sandbox": round(max((s.risk for s in sandbox), default=0), 3) or None,
        "vision": round(res.vision.risk, 3) if res.vision else None,
    }
    det_signals = []
    sig_report = getattr(res, "signals", None)
    if sig_report is not None:
        det_signals = [{"name": s.name, "severity": s.severity,
                        "detail": s.detail, "evidence": s.evidence}
                       for s in sig_report.signals]
    timings = getattr(res, "stage_timings", None) or {}
    sender, preview = _maybe_redact(
        (triage.sender if triage else "")[:200], (body or "")[:400])
    conn = _connect(path)
    try:
        conn.execute(
            """INSERT INTO verdicts
               (email_id, received_at, sender, label, confidence, score,
                contributions, dissent, red_flags, campaign_note, signals,
                body_preview, det_signals, timings)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(email_id) DO UPDATE SET
                 received_at=excluded.received_at, sender=excluded.sender,
                 label=excluded.label, confidence=excluded.confidence,
                 score=excluded.score, contributions=excluded.contributions,
                 dissent=excluded.dissent, red_flags=excluded.red_flags,
                 campaign_note=excluded.campaign_note,
                 signals=excluded.signals,
                 body_preview=excluded.body_preview,
                 det_signals=excluded.det_signals,
                 timings=excluded.timings""",
            (res.email_id,
             datetime.now(timezone.utc).isoformat(),
             sender,
             v.label.value if v else "",
             round(v.confidence, 2) if v else 0,
             round(v.score, 3) if v else 0,
             json.dumps(v.contributions if v else {}),
             json.dumps(v.dissent if v else []),
             json.dumps(flags),
             res.campaign_note or "",
             json.dumps(signals),
             preview,
             json.dumps(det_signals),
             json.dumps(timings),
             ),
        )
        conn.commit()
    finally:
        conn.close()


def list_verdicts(limit: int = 50,
                  path: str = "data/dashboard.db") -> list[dict]:
    conn = _connect(path)
    try:
        rows = conn.execute(
            "SELECT * FROM verdicts ORDER BY received_at DESC LIMIT ?",
            (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_verdict(email_id: str,
                path: str = "data/dashboard.db") -> dict | None:
    conn = _connect(path)
    try:
        row = conn.execute("SELECT * FROM verdicts WHERE email_id = ?",
                           (email_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def stats(path: str = "data/dashboard.db") -> dict:
    conn = _connect(path)
    try:
        total = conn.execute("SELECT COUNT(*) c FROM verdicts").fetchone()["c"]
        by_label = {r["label"]: r["c"] for r in conn.execute(
            "SELECT label, COUNT(*) c FROM verdicts GROUP BY label")}
        return {"total": total, "by_label": by_label}
    finally:
        conn.close()
