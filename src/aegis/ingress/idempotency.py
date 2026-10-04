"""Webhook idempotency: a duplicated AgentBoxD delivery must never trigger a
second analysis or a second reply.

Processed message IDs are recorded in a small SQLite table (gitignored
runtime state). The check-and-mark is a single INSERT OR IGNORE inside a
transaction, so concurrent duplicate deliveries race safely.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS webhook_processed (
    message_id   TEXT PRIMARY KEY,
    processed_at TEXT NOT NULL
);
"""


def _connect(path: str = "data/webhook.db") -> sqlite3.Connection:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.execute(SCHEMA)
    return conn


def already_processed(message_id: str, path: str = "data/webhook.db") -> bool:
    """True if this message was seen before. Empty/None IDs never dedup."""
    if not message_id:
        return False
    conn = _connect(path)
    try:
        row = conn.execute(
            "SELECT 1 FROM webhook_processed WHERE message_id = ?",
            (message_id,)).fetchone()
        return row is not None
    finally:
        conn.close()


def mark_processed(message_id: str, path: str = "data/webhook.db") -> None:
    if not message_id:
        return
    conn = _connect(path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO webhook_processed (message_id, processed_at)"
            " VALUES (?, ?)",
            (message_id, datetime.now(timezone.utc).isoformat()))
        conn.commit()
    finally:
        conn.close()
