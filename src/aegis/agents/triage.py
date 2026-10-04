"""AEGIS-Triage: fast entity extraction. Zero judgement — extraction only."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import get_settings
from ..llm import chat_json

TRIAGE_SYSTEM = """You are AEGIS-Triage, stage 1 of a scam-detection pipeline.
Extract structured entities from the raw email below. Return ONLY valid JSON
matching this schema — no prose, no markdown fences:

{
  "sender": "display name + address as shown",
  "reply_to": "reply-to address or empty string",
  "urls": ["every URL found, in order"],
  "domains": ["unique domains from urls + sender, lowercased"],
  "phone_numbers": ["..."],
  "attachment_names": ["..."],
  "urgency_signals": ["short quotes like 'act within 24 hours'"],
  "requested_action": "one line: what the email wants the reader to do",
  "language": "en",
  "brand_mentions": ["brands named or implied, e.g. PayPal"]
}

Rules:
- Extract, do not judge. Never label anything a scam.
- If a field has nothing, use "" or [] — never null, never invent values.
- Preserve URLs exactly as written, including punycode and odd ports."""


@dataclass
class TriageResult:
    sender: str = ""
    reply_to: str = ""
    urls: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    phone_numbers: list[str] = field(default_factory=list)
    attachment_names: list[str] = field(default_factory=list)
    urgency_signals: list[str] = field(default_factory=list)
    requested_action: str = ""
    language: str = "en"
    brand_mentions: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "TriageResult":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


def triage(raw_email: str, headers: str = "") -> TriageResult:
    """Run triage on one raw email. Returns structured entities."""
    model = get_settings().model_triage
    user_msg = f"HEADERS:\n{headers}\n\nBODY:\n{raw_email}"
    data = chat_json(
        model,
        [
            {"role": "system", "content": TRIAGE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
    )
    return TriageResult.from_dict(data)
