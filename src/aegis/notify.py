"""Outbound mail via the AgentBoxD REST API.

- reply_to_message: direct verdict-card reply, stays in the thread.
- create_draft_reply: human-in-the-loop — a person approves in the dashboard.
- get_message: fetch full content when the webhook carried an envelope only.

Docs: https://agentboxd.com/docs/api
Base: https://api.agentboxd.com, Authorization: Bearer <AGENTBOXD_API_KEY>.
"""
from __future__ import annotations

import uuid

import httpx

from .config import agentboxd_api_key

BASE_URL = "https://api.agentboxd.com"


def _client() -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {agentboxd_api_key()}"},
        timeout=30.0,
    )


def reply_to_message(inbox_id: str, message_id: str, text: str) -> dict:
    """POST /v1/inboxes/:id/messages/:messageId/reply — idempotent."""
    with _client() as c:
        r = c.post(
            f"/v1/inboxes/{inbox_id}/messages/{message_id}/reply",
            json={"text": text},
            headers={"Idempotency-Key": f"aegis-reply-{message_id}"},
        )
        r.raise_for_status()
        return r.json()


def create_draft_reply(inbox_id: str, message_id: str, text: str) -> dict:
    """POST /v1/inboxes/:id/drafts with reply_to_message_id — needs a human."""
    with _client() as c:
        r = c.post(
            f"/v1/inboxes/{inbox_id}/drafts",
            json={"reply_to_message_id": message_id, "text": text},
            headers={"Idempotency-Key": f"aegis-draft-{uuid.uuid4().hex[:8]}"},
        )
        r.raise_for_status()
        return r.json()


def get_message(message_id: str) -> dict:
    """GET /v1/messages/:id — full content when the webhook was envelope-only."""
    with _client() as c:
        r = c.get(f"/v1/messages/{message_id}")
        r.raise_for_status()
        return r.json()


def message_scores(msg: dict) -> dict:
    """Extract the AgentBoxD phishing/injection signals from a message payload.

    Prefers numeric scores when present; falls back to the ai:* labels.
    """
    scores = msg.get("scores") or {}
    labels = msg.get("labels") or []
    phishing = scores.get("phishing")
    if phishing is None and "ai:phishing" in labels:
        phishing = 0.9
    injection = scores.get("injection") or scores.get("prompt_injection")
    if injection is None and "ai:injection-risk" in labels:
        injection = 0.9
    return {"phishing": phishing, "injection": injection}
