"""FastAPI receiver for AgentBoxD signed webhooks.

AgentBoxD signs every webhook body with HMAC-SHA256 using the workspace
webhook secret, delivered in the X-Mailroom-Signature header.
Unsigned / bad-signature events are rejected with 401 — fail closed.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from ..config import get_settings

app = FastAPI(title="AEGIS ingress")


def verify_signature(body: bytes, signature: str | None, secret: str) -> bool:
    if not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "aegis-ingress"}


@app.post("/webhook/agentboxd")
async def agentboxd_webhook(
    request: Request,
    x_mailroom_signature: str | None = Header(default=None),
) -> JSONResponse:
    body = await request.body()
    secret = get_settings().agentboxd_webhook_secret
    if not verify_signature(body, x_mailroom_signature, secret):
        raise HTTPException(status_code=401, detail="bad webhook signature")

    event = json.loads(body)
    # Persist the raw event; the orchestrator picks it up from here.
    os.makedirs("data/inbox", exist_ok=True)
    msg_id = event.get("id") or event.get("message_id") or "unknown"
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    path = f"data/inbox/{ts}_{msg_id}.json"
    with open(path, "w") as f:
        json.dump(event, f, indent=2)

    # TODO (Phase 1): enqueue → orchestrator.analyze_email(event)
    return JSONResponse({"ok": True, "stored": path})
