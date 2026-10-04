"""Dashboard verdict store: SQLite record of every analyzed email.

Written by the webhook receiver after each analysis (and by demo scripts);
read by the dashboard API. `data/*.db` is gitignored runtime state.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone

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
    body_preview TEXT DEFAULT ''
);
"""


def _connect(path: str = "data/dashboard.db") -> sqlite3.Connection:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
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
    conn = _connect(path)
    try:
        conn.execute(
            """INSERT INTO verdicts
               (email_id, received_at, sender, label, confidence, score,
                contributions, dissent, red_flags, campaign_note, signals,
                body_preview)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(email_id) DO UPDATE SET
                 received_at=excluded.received_at, sender=excluded.sender,
                 label=excluded.label, confidence=excluded.confidence,
                 score=excluded.score, contributions=excluded.contributions,
                 dissent=excluded.dissent, red_flags=excluded.red_flags,
                 campaign_note=excluded.campaign_note,
                 signals=excluded.signals,
                 body_preview=excluded.body_preview""",
            (res.email_id,
             datetime.now(timezone.utc).isoformat(),
             (triage.sender if triage else "")[:200],
             v.label.value if v else "",
             round(v.confidence, 2) if v else 0,
             round(v.score, 3) if v else 0,
             json.dumps(v.contributions if v else {}),
             json.dumps(v.dissent if v else []),
             json.dumps(flags),
             res.campaign_note or "",
             json.dumps(signals),
             (body or "")[:400]),
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
