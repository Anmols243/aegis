"""AEGIS-Triage: fast entity extraction. Zero judgement — extraction only."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import get_settings
from ..config import get_settings
from ..llm import chat_json
from .validate import (UNTRUSTED_DATA_RULES, as_str_list, sanitize,
                       wrap_untrusted)

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
- Preserve URLs exactly as written, including punycode and odd ports.
""" + UNTRUSTED_DATA_RULES


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
        """Typed coercion — the model is untrusted, so junk is dropped,
        never propagated into the pipeline."""
        if not isinstance(d, dict):
            raise ValueError("triage output is not a JSON object")
        known = set(cls.__dataclass_fields__)
        clean: dict = {}
        for k, v in d.items():
            if k not in known:
                continue
            if k in ("urls", "domains", "phone_numbers", "attachment_names",
                     "urgency_signals", "brand_mentions"):
                clean[k] = as_str_list(v)
            else:
                clean[k] = sanitize(v) if isinstance(v, str) else ""
        # Domains: lowercase + dedup, as the schema promises.
        clean["domains"] = list(dict.fromkeys(
            x.lower() for x in clean.get("domains", [])))
        return cls(**clean)


def triage(raw_email: str, headers: str = "") -> TriageResult:
    """Run triage on one raw email. Returns structured entities."""
    model = get_settings().model_triage
    # The email is wrapped as UNTRUSTED DATA — never bare instructions.
    user_msg = (f"HEADERS:\n{headers}\n\n"
                f"BODY:\n{wrap_untrusted(raw_email)}")
    data = chat_json(
        model,
        [
            {"role": "system", "content": TRIAGE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
    )
    return TriageResult.from_dict(data)
