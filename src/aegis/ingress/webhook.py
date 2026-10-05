"""FastAPI receiver for AgentBoxD signed webhooks.

AgentBoxD signs every webhook body with HMAC-SHA256 using the workspace
webhook secret, delivered in the X-Mailroom-Signature header.
Unsigned / bad-signature events are rejected with 401 — fail closed.

On a valid event the raw payload is stored and the pipeline runs in the
background; the verdict card is replied in-thread via the AgentBoxD API.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import threading
import traceback
from datetime import datetime, timezone

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from .. import notify
from ..config import agentboxd_webhook_secret
from ..middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from ..orchestrator import analyze_email
from .idempotency import already_processed, mark_processed

app = FastAPI(title="AEGIS ingress")
app.add_middleware(SecurityHeadersMiddleware)
# Webhooks are infrequent and each one is expensive (full LLM pipeline):
# 10/min sustained, burst 20. Bursts beyond that get 429 + Retry-After.
app.add_middleware(RateLimitMiddleware, rate=10.0, per_seconds=60.0,
                   burst=20)

# Reject absurd payloads before parsing — an AgentBoxD webhook envelope
# carrying a full message is kilobytes; 5MB is generous headroom.
MAX_WEBHOOK_BYTES = 5 * 1024 * 1024

# Each accepted webhook spawns a full multi-agent analysis (LLM calls).
# Bound concurrent analyses so a burst can't exhaust the box; excess
# deliveries are rejected with 429 and AgentBoxD will redeliver.
MAX_CONCURRENT_ANALYSES = 4
_analysis_slots = threading.BoundedSemaphore(MAX_CONCURRENT_ANALYSES)


def _audit(event: str, **fields) -> None:
    """Append-only JSON-lines audit trail for ingress decisions."""
    try:
        os.makedirs("data", exist_ok=True)
        rec = {"ts": datetime.now(timezone.utc).isoformat(),
               "event": event, **fields}
        with open("data/audit.log", "a") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError:
        pass


def verify_signature(body: bytes, signature: str | None, secret: str) -> bool:
    if not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _message_ref(event: dict) -> tuple[str | None, str | None]:
    """Best-effort (inbox_id, message_id) extraction across event shapes."""
    d = event.get("data", event) if isinstance(event, dict) else {}
    msg = d.get("message", d) if isinstance(d, dict) else {}
    if not isinstance(msg, dict):
        msg = {}
    message_id = msg.get("id") or d.get("message_id") or event.get("message_id")
    inbox_id = (msg.get("inbox_id") or d.get("inbox_id")
                or event.get("inbox_id") or os.environ.get("AEGIS_INBOX_ID"))
    return inbox_id, message_id


def _extract_content(event: dict) -> dict | None:
    """Inline content if the webhook carried it; None if envelope-only."""
    d = event.get("data", event) if isinstance(event, dict) else {}
    msg = d.get("message", d) if isinstance(d, dict) else {}
    if not isinstance(msg, dict):
        return None
    text = msg.get("text") or msg.get("extracted_text") or ""
    if not text and not msg.get("html"):
        return None
    return msg


def _process(inbox_id: str, message_id: str, event: dict) -> None:
    try:
        _run_process(inbox_id, message_id, event)
    finally:
        _analysis_slots.release()


def _run_process(inbox_id: str, message_id: str, event: dict) -> None:
    try:
        msg = _extract_content(event)
        if msg is None:  # envelope payload — fetch the full message
            msg = notify.get_message(message_id)
        body = msg.get("text") or msg.get("extracted_text") or ""
        headers = msg.get("headers") or ""
        html = msg.get("html") or ""
        res = analyze_email(message_id, body, headers, html,
                            notify.message_scores(msg))
        try:
            from ..dashboard.store import record as record_verdict
            record_verdict(res, body)
        except Exception as e:  # noqa: BLE001 — dashboard must never break replies
            print(f"[aegis] dashboard record failed: {e}", file=sys.stderr)
        notify.reply_to_message(inbox_id, message_id, res.card_markdown)
        print(f"[aegis] replied to {message_id}: {res.verdict.label.value}",
              file=sys.stderr)
    except Exception:  # noqa: BLE001 — never crash the webhook worker
        os.makedirs("data/errors", exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        with open(f"data/errors/{ts}_{message_id}.log", "w") as f:
            f.write(traceback.format_exc())


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "aegis-ingress"}


@app.post("/webhook/agentboxd")
async def agentboxd_webhook(
    request: Request,
    background: BackgroundTasks,
    x_mailroom_signature: str | None = Header(default=None),
) -> JSONResponse:
    body = await request.body()
    if len(body) > MAX_WEBHOOK_BYTES:
        raise HTTPException(status_code=413, detail="webhook payload too large")
    secret = agentboxd_webhook_secret()
    if not verify_signature(body, x_mailroom_signature, secret):
        _audit("webhook_bad_signature",
               remote=request.client.host if request.client else "?")
        raise HTTPException(status_code=401, detail="bad webhook signature")

    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400,
                            detail="malformed webhook JSON") from None
    if not isinstance(event, dict):
        raise HTTPException(status_code=400,
                            detail="webhook body must be a JSON object")

    inbox_id, message_id = _message_ref(event)

    # Idempotency: a redelivered webhook is acknowledged, not reprocessed.
    if message_id and already_processed(message_id):
        return JSONResponse({"ok": True, "duplicate": True})

    os.makedirs("data/inbox", exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    path = f"data/inbox/{ts}_{message_id or 'unknown'}.json"
    with open(path, "w") as f:
        json.dump(event, f, indent=2)

    if inbox_id and message_id:
        if not _analysis_slots.acquire(blocking=False):
            _audit("webhook_saturated", message_id=message_id)
            raise HTTPException(
                status_code=429,
                detail="analysis pipeline saturated, redeliver later")
        mark_processed(message_id)
        background.add_task(_process, inbox_id, message_id, event)
        _audit("webhook_accepted", message_id=message_id, inbox_id=inbox_id)
    else:
        _audit("webhook_missing_ids", stored=path)
    return JSONResponse({"ok": True, "stored": path})
