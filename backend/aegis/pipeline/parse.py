"""Stage 0: turn pasted text or an .eml source into an EmailArtifact.

Pure stdlib parsing. Handles full RFC 822 messages (multipart, encoded
headers, HTML-only mail), a pasted "Header: value" block followed by a body,
and plain body text with no headers at all.
"""
from __future__ import annotations

import html as html_lib
import re
from email import policy
from email.parser import Parser

from .context import EmailArtifact, PipelineContext, StageResult

_HEADER_LINE = re.compile(r"^[A-Za-z][A-Za-z0-9-]{1,40}:\s?.*$")
_KNOWN = {"from", "to", "subject", "date", "reply-to", "received", "return-path",
          "message-id", "mime-version", "content-type", "authentication-results", "cc"}


def looks_like_headers(raw: str) -> bool:
    """True when the input starts with a header block naming known headers."""
    lines = raw.lstrip().splitlines()
    known = 0
    for line in lines[:60]:
        if not line.strip():
            break
        if line[:1] in " \t":
            continue  # folded header continuation
        if not _HEADER_LINE.match(line):
            return False
        if line.split(":", 1)[0].strip().lower() in _KNOWN:
            known += 1
    return known >= 1


def html_to_text(html: str) -> str:
    t = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", " ", html or "")
    t = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</h\d>|</li>", "\n", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html_lib.unescape(t)
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n\n", t).strip()


def parse_email(raw: str, raw_html: str = "") -> EmailArtifact:
    raw = (raw or "").replace("\r\n", "\n")
    art = EmailArtifact(raw=raw)
    if looks_like_headers(raw):
        msg = Parser(policy=policy.default).parsestr(raw.lstrip())
        art.headers = "\n".join(f"{k}: {v}" for k, v in msg.items())
        art.subject = str(msg.get("Subject", "") or "")
        art.sender = str(msg.get("From", "") or "")
        art.reply_to = str(msg.get("Reply-To", "") or "")
        art.to = str(msg.get("To", "") or "")
        art.date = str(msg.get("Date", "") or "")
        art.message_id = str(msg.get("Message-ID", "") or "")
        try:
            if msg.is_multipart() or msg.get_content_type().startswith("text/"):
                plain = msg.get_body(preferencelist=("plain",))
                rich = msg.get_body(preferencelist=("html",))
                art.text = plain.get_content() if plain is not None else ""
                art.html = rich.get_content() if rich is not None else ""
                art.attachments = [p.get_filename() or "(unnamed)"
                                   for p in msg.iter_attachments()]
            else:
                art.text = str(msg.get_payload(decode=False) or "")
        except (KeyError, LookupError, AttributeError):
            # malformed MIME: fall back to whatever follows the header block
            art.text = raw.split("\n\n", 1)[1] if "\n\n" in raw else ""
    else:
        art.text = raw
    if raw_html and not art.html:
        art.html = raw_html
    if not art.text.strip() and art.html:
        art.text = html_to_text(art.html)
    elif not art.html and re.search(r"(?i)<a\s[^>]*href=", art.text):
        # pasted HTML fragments (e.g. a link with different display text)
        art.html = art.text
    art.text = art.text.strip()
    if not art.subject:
        first = next((ln.strip() for ln in art.text.splitlines() if ln.strip()), "")
        art.subject = first[:120]
    return art


async def run(ctx: PipelineContext) -> StageResult:
    ctx.email = parse_email(ctx.raw, ctx.raw_html)
    e = ctx.email
    bits = [f"{len(e.text)} chars of text"]
    if e.headers:
        bits.append(f"{len(e.headers.splitlines())} header lines")
    if e.html:
        bits.append("HTML part")
    if e.attachments:
        bits.append(f"{len(e.attachments)} attachment(s)")
    return StageResult(e, ", ".join(bits))
