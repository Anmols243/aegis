"""Stage 1: entity extraction. Zero judgement.

The LLM extracts semantic entities (urgency phrases, requested action, brand
mentions, phone numbers). Deterministic extraction always runs too and is
merged in, so a URL or sender the model skipped is never lost; if the model
is unreachable the deterministic result alone is used (marked degraded).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from .context import PipelineContext, StageResult
from .validate import UNTRUSTED_DATA_RULES, as_str_list, prose, sanitize, wrap_untrusted

SYSTEM = """You are AEGIS-Triage, stage 1 of a scam-detection pipeline.
Extract structured entities from the email. Return ONLY a JSON object:

{
  "urls": ["every URL, exactly as written"],
  "phone_numbers": ["..."],
  "urgency_signals": ["short exact quotes like 'within 24 hours'"],
  "requested_action": "one line: what the email wants the reader to do",
  "language": "ISO code, e.g. en",
  "brand_mentions": ["companies or institutions named or implied, e.g. PayPal"]
}

Rules:
- Extract, do not judge. Never label anything a scam.
- Empty fields are "" or []. Never invent values.
""" + UNTRUSTED_DATA_RULES

_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
_HREF_RE = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\w)(\+?\d[\d\s().-]{7,}\d)(?!\w)")
_EMAIL_DOMAIN = re.compile(r"@([\w.-]+\.[a-z]{2,})", re.IGNORECASE)


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
    degraded: bool = False

    def entity_count(self) -> int:
        return (len(self.urls) + len(self.domains) + len(self.phone_numbers)
                + len(self.attachment_names) + len(self.brand_mentions))


def _dedup(items) -> list[str]:
    return list(dict.fromkeys(i for i in items if i))


def deterministic(email) -> TriageResult:
    urls = _URL_RE.findall(email.text or "") + [
        u for u in _HREF_RE.findall(email.html or "") if u.lower().startswith(("http://", "https://"))]
    urls = _dedup(u.rstrip(".,;:") for u in urls)
    domains = [(urlsplit(u).hostname or "").lower() for u in urls]
    m = _EMAIL_DOMAIN.search(email.sender or "")
    if m:
        domains.append(m.group(1).lower())
    phones = _dedup(p.strip() for p in _PHONE_RE.findall(email.text or "")
                    if 7 <= len(re.sub(r"\D", "", p)) <= 15)
    return TriageResult(sender=email.sender, reply_to=email.reply_to, urls=urls,
                        domains=_dedup(domains), phone_numbers=phones,
                        attachment_names=list(email.attachments))


async def run(ctx: PipelineContext) -> StageResult:
    email = ctx.email
    base = deterministic(email)
    try:
        data = await ctx.llm.chat_json(ctx.settings.model_triage, [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"HEADERS:\n{email.headers}\n\n"
                                        f"SUBJECT: {email.subject}\n\n"
                                        f"BODY:\n{wrap_untrusted(email.text)}"},
        ])
    except Exception as e:  # noqa: BLE001 - model down or bad output: degrade, don't die
        base.degraded = True
        return StageResult(base, f"model unavailable ({type(e).__name__}); "
                                 f"deterministic extraction: {base.entity_count()} entities")
    llm_urls = [u for u in as_str_list(data.get("urls"))
                if u.lower().startswith(("http://", "https://"))]
    base.urls = _dedup(base.urls + llm_urls)
    base.domains = _dedup(base.domains + [(urlsplit(u).hostname or "").lower() for u in llm_urls])
    base.phone_numbers = _dedup(base.phone_numbers + as_str_list(data.get("phone_numbers")))
    base.urgency_signals = as_str_list(data.get("urgency_signals"))
    base.requested_action = prose(data.get("requested_action"), 300)
    base.language = sanitize(data.get("language"), 8) or "en"
    base.brand_mentions = as_str_list(data.get("brand_mentions"), max_items=10, max_len=60)
    return StageResult(base, f"{base.entity_count()} entities, "
                             f"{len(base.urgency_signals)} urgency cue(s)")
