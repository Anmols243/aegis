"""AgentBoxD REST client: fetch messages, long-poll the inbox, reply in-thread.

Base URL https://api.agentboxd.com, `Authorization: Bearer <AGENTBOXD_API_KEY>`.
"""
from __future__ import annotations

import hashlib
import hmac

import httpx

from ..core.config import Settings


def verify_signature(body: bytes, signature: str | None, secret: str) -> bool:
    """HMAC-SHA256 hex over the raw body, compared in constant time."""
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())


def message_scores(msg: dict) -> dict:
    """AgentBoxD's own per-message phishing / prompt-injection signals.

    Prefers numeric scores; falls back to the ai:* labels."""
    scores = msg.get("scores") or {}
    labels = msg.get("labels") or []
    phishing = scores.get("phishing")
    if phishing is None and "ai:phishing" in labels:
        phishing = 0.9
    injection = scores.get("injection") or scores.get("prompt_injection")
    if injection is None and "ai:injection-risk" in labels:
        injection = 0.9
    out = {}
    for k, v in (("phishing", phishing), ("injection", injection)):
        try:
            if v is not None:
                out[k] = max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            pass
    return out


def message_to_raw(msg: dict) -> tuple[str, str]:
    """(raw rfc822-ish text, html) from an AgentBoxD message object."""
    headers = msg.get("headers") or ""
    if isinstance(headers, dict):
        headers = "\n".join(f"{k}: {v}" for k, v in headers.items())
    if not headers:
        lines = []
        for key, name in (("from", "From"), ("to", "To"), ("subject", "Subject"),
                          ("reply_to", "Reply-To"), ("date", "Date")):
            val = msg.get(key)
            if isinstance(val, dict):
                val = val.get("address") or val.get("email") or ""
            if val:
                lines.append(f"{name}: {val}")
        headers = "\n".join(lines)
    body = msg.get("text") or msg.get("extracted_text") or ""
    return (f"{headers}\n\n{body}" if headers else body), (msg.get("html") or "")


class AgentBoxD:
    def __init__(self, settings: Settings):
        self.s = settings

    @property
    def configured(self) -> bool:
        return self.s.agentboxd_configured

    def _client(self, timeout: float = 30.0) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.s.agentboxd_base_url, timeout=timeout,
                                 headers={"Authorization": f"Bearer {self.s.agentboxd_api_key}"})

    async def get_message(self, message_id: str) -> dict:
        async with self._client() as c:
            r = await c.get(f"/v1/messages/{message_id}")
            r.raise_for_status()
            data = r.json()
            return data.get("data", data) if isinstance(data, dict) else {}

    async def wait_inbound(self, since: str | None, timeout_s: int = 60) -> dict | None:
        params: dict = {"timeout": timeout_s, "direction": "inbound"}
        if since:
            params["since"] = since
        async with self._client(timeout=timeout_s + 10) as c:
            r = await c.get(f"/v1/inboxes/{self.s.agentboxd_inbox_id}/messages/wait",
                            params=params)
            r.raise_for_status()
            return r.json().get("data")

    async def reply(self, inbox_id: str, message_id: str, text: str) -> None:
        async with self._client() as c:
            r = await c.post(f"/v1/inboxes/{inbox_id}/messages/{message_id}/reply",
                             json={"text": text},
                             headers={"Idempotency-Key": f"aegis-reply-{message_id}"})
            r.raise_for_status()
