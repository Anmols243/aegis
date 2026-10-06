"""Deterministic security signals: verified facts, zero LLM.

The LLM stages reason; this layer measures. Every check below is a pure
function over the email artifact: headers, body, HTML, and triage entities.
No model calls, no hallucinations, fully unit-testable.

The signals are fed to the forensic analyst as verified context (so it
reasons over facts instead of re-deriving them) and surfaced on the verdict
card and dashboard as their own evidence section.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import unquote, urlparse

SEVERITIES = {"high", "medium", "low", "info"}


@dataclass
class Signal:
    name: str        # machine key, e.g. "punycode-domain"
    severity: str    # high | medium | low | info
    detail: str      # human-readable, judge-friendly
    evidence: str    # quoted artifact excerpt (capped)


@dataclass
class SignalReport:
    signals: list[Signal] = field(default_factory=list)

    @property
    def by_severity(self) -> dict[str, list[Signal]]:
        out: dict[str, list[Signal]] = {}
        for s in self.signals:
            out.setdefault(s.severity, []).append(s)
        return out

    @property
    def risk(self) -> float:
        """Deterministic 0..1 contribution, noisy-OR over severities.

        Each signal is treated as independent evidence: one high signal gives
        0.6, two give 0.84, a lone low signal 0.1. Info signals (e.g. SPF pass)
        contribute nothing.
        """
        weights = {"high": 0.6, "medium": 0.3, "low": 0.1, "info": 0.0}
        p_clean = 1.0
        for s in self.signals:
            p_clean *= 1.0 - weights.get(s.severity, 0.0)
        return round(1.0 - p_clean, 3)

    @property
    def high(self) -> list[Signal]:
        return [s for s in self.signals if s.severity == "high"]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _sig(name: str, severity: str, detail: str, evidence: str) -> Signal:
    return Signal(name, severity, detail, evidence[:200])


def _domains_of(urls: list[str]) -> list[str]:
    out = []
    for u in urls:
        try:
            h = urlparse(u).hostname or ""
        except Exception:
            continue
        if h:
            out.append(h.lower())
    return out


# ---------------------------------------------------------------------------
# individual checks: each is a pure function, unit-tested
# ---------------------------------------------------------------------------

def check_auth_results(headers: str) -> list[Signal]:
    """Parse Authentication-Results for SPF/DKIM/DMARC verdicts."""
    sigs = []
    for m in re.finditer(
            r"authentication-results:[^\n]*(?:\n[ \t]+[^\n]*)*",
            headers, re.IGNORECASE):
        block = m.group(0).lower()
        for mech in ("spf", "dkim", "dmarc"):
            mm = re.search(rf"\b{mech}=(\w+)", block)
            if mm:
                result = mm.group(1)
                if result in ("fail", "softfail", "temperror", "permerror",
                              "none"):
                    sev = "high" if result == "fail" else "medium"
                    sigs.append(_sig(
                        f"{mech}-{result}", sev,
                        f"Email authentication {mech.upper()} did not pass "
                        f"({result}).",
                        m.group(0)[:200]))
                elif result == "pass":
                    sigs.append(_sig(f"{mech}-pass", "info",
                                     f"{mech.upper()} passed.", ""))
    return sigs


def check_from_replyto(sender: str, reply_to: str) -> list[Signal]:
    """From vs Reply-To domain mismatch: classic phish redirect."""
    def domain(addr: str) -> str:
        m = re.search(r"@([\w.\-]+)", addr or "")
        return m.group(1).lower() if m else ""

    d_from, d_reply = domain(sender), domain(reply_to)
    if d_from and d_reply and d_from != d_reply:
        return [_sig("from-replyto-mismatch", "high",
                     f"Reply-To domain ({d_reply}) differs from From domain "
                     f"({d_from}): replies go to the attacker.",
                     f"From: {sender} / Reply-To: {reply_to}")]
    return []


_BRAND_DOMAINS = {
    # brand token -> legitimate domains (subset; extend as needed)
    "paypal": {"paypal.com"},
    "apple": {"apple.com", "icloud.com"},
    "microsoft": {"microsoft.com", "outlook.com", "live.com"},
    "google": {"google.com", "gmail.com"},
    "amazon": {"amazon.com"},
    "netflix": {"netflix.com"},
    "dhl": {"dhl.com"},
    "fedex": {"fedex.com"},
    "ups": {"ups.com"},
}


def check_display_name_spoof(sender: str) -> list[Signal]:
    """Display name claims a brand the sender domain doesn't own."""
    m = re.match(r"\s*(.*?)\s*<([^>]+)>", sender or "")
    if not m:
        return []
    display, addr = m.group(1).strip().lower(), m.group(2).lower()
    sender_domain = addr.split("@")[-1] if "@" in addr else ""
    for brand, legit in _BRAND_DOMAINS.items():
        if brand in display and sender_domain not in legit:
            return [_sig("display-name-spoof", "high",
                         f"Display name claims '{brand.title()}' but the "
                         f"sender domain is {sender_domain}.",
                         sender[:200])]
    return []


def check_sender_link_mismatch(sender: str, urls: list[str]) -> list[Signal]:
    """None of the link domains match the sender domain."""
    m = re.search(r"@([\w.\-]+)", sender or "")
    sender_domain = m.group(1).lower() if m else ""
    link_domains = _domains_of(urls)
    if sender_domain and link_domains and not any(
            d == sender_domain or d.endswith("." + sender_domain)
            for d in link_domains):
        return [_sig("sender-link-domain-mismatch", "medium",
                     f"Links point to {link_domains[0]} but the mail claims "
                     f"to be from {sender_domain}.",
                     urls[0][:200])]
    return []


def check_url_display_mismatch(html: str) -> list[Signal]:
    """Anchor text shows one URL, href goes somewhere else."""
    sigs = []
    for m in re.finditer(
            r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            html or "", re.IGNORECASE | re.DOTALL):
        href, text = m.group(1).strip(), re.sub(r"<[^>]+>", "", m.group(2))
        text = text.strip()
        if re.match(r"https?://\S+", text):
            try:
                h_href = (urlparse(href).hostname or "").lower()
                h_text = (urlparse(text).hostname or "").lower()
            except Exception:
                continue
            if h_href and h_text and h_href != h_text:
                sigs.append(_sig(
                    "url-display-mismatch", "high",
                    "Link text shows one destination, the href goes "
                    "somewhere else.",
                    f"text: {text[:80]} → href: {href[:120]}"))
    return sigs


def check_punycode(domains: list[str]) -> list[Signal]:
    sigs = []
    for d in domains:
        if "xn--" in d.lower():
            sigs.append(_sig("punycode-domain", "high",
                             f"Internationalized domain {d}: classic "
                             f"homoglyph-attack encoding.",
                             d[:200]))
    return sigs


# Common Cyrillic/Greek confusables mapped to their ASCII lookalike.
_CONFUSABLES = str.maketrans({
    "а": "a", "е": "e", "і": "i", "о": "o", "р": "p", "с": "c", "х": "x",
    "у": "y", "ѕ": "s", "ԁ": "d", "һ": "h", "ј": "j", "ӏ": "l", "ո": "n",
    "ԛ": "q", "ԝ": "w", "ᴠ": "v", "ᴢ": "z", "β": "b", "ɡ": "g", "κ": "k",
    "μ": "m", "ν": "v", "τ": "t", "ρ": "p", "ω": "w", "ﬁ": "fi",
})


def check_homoglyph(domains: list[str], brands: list[str]) -> list[Signal]:
    """Non-ASCII confusable characters in domains or brand mentions."""
    sigs = []
    for d in domains:
        folded = d.translate(_CONFUSABLES)
        if folded != d:
            sigs.append(_sig("homoglyph-domain", "high",
                             f"Domain {d} contains Unicode lookalike "
                             f"characters (renders as {folded}).",
                             d[:200]))
    for b in brands or []:
        folded = b.translate(_CONFUSABLES)
        if folded != b:
            sigs.append(_sig("homoglyph-brand", "high",
                             f"Brand mention {b} uses lookalike characters "
                             f"(renders as {folded}).",
                             b[:200]))
    return sigs


def check_ip_literal_url(urls: list[str]) -> list[Signal]:
    import ipaddress
    sigs = []
    for u in urls:
        try:
            host = (urlparse(u).hostname or "")
            ipaddress.ip_address(host)
            sigs.append(_sig("ip-literal-url", "high",
                             "Link uses a raw IP address instead of a "
                             "domain: evades domain reputation.",
                             u[:200]))
        except ValueError:
            continue
    return sigs


_SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
               "buff.ly", "rebrand.ly", "cutt.ly", "shorte.st"}


def check_url_shortener(urls: list[str]) -> list[Signal]:
    sigs = []
    for d in _domains_of(urls):
        if d in _SHORTENERS or d.startswith("bit.ly"):
            sigs.append(_sig("url-shortener", "medium",
                             f"Link hides its destination behind shortener "
                             f"{d}.",
                             d[:200]))
    return sigs


_SUSPICIOUS_TLDS = {".xyz", ".top", ".club", ".online", ".site", ".icu",
                    ".buzz", ".rest", ".sbs", ".cyou", ".quest"}


def check_suspicious_tld(domains: list[str]) -> list[Signal]:
    sigs = []
    for d in domains:
        dl = d.lower()
        if any(dl.endswith(t) for t in _SUSPICIOUS_TLDS):
            sigs.append(_sig("suspicious-tld", "low",
                             f"Domain {d} uses a TLD heavily abused by "
                             f"phishing campaigns.",
                             d[:200]))
    return sigs


def check_encoded_url_tricks(urls: list[str]) -> list[Signal]:
    sigs = []
    for u in urls:
        try:
            p = urlparse(u)
        except Exception:
            continue
        # userinfo (@) trick: https://paypal.com@evil.com/
        if "@" in (p.netloc or ""):
            sigs.append(_sig("url-userinfo-trick", "high",
                             "URL embeds credentials/userinfo to disguise "
                             "the real host.",
                             u[:200]))
            continue
        # heavy percent-encoding of the host/path
        if u.count("%") >= 4 or "%2e" in u.lower() or "%2f" in u.lower():
            sigs.append(_sig("encoded-url", "medium",
                             "URL uses heavy percent-encoding to obscure "
                             "its destination.",
                             u[:200]))
    return sigs


_EXECUTABLE_EXTS = {".exe", ".msi", ".dmg", ".apk", ".scr", ".bat", ".ps1",
                    ".js", ".vbs", ".jar", ".iso", ".img", ".lnk", ".hta",
                    ".dll", ".com", ".pif"}
_ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz"}


def check_attachments(names: list[str]) -> list[Signal]:
    """Static attachment triage: no detonation, just metadata."""
    sigs = []
    for n in names or []:
        low = n.lower().strip()
        # double extension: invoice.pdf.exe
        parts = low.split(".")
        if len(parts) > 2 and f".{parts[-1]}" in _EXECUTABLE_EXTS:
            sigs.append(_sig("attachment-double-extension", "high",
                             f"Attachment {n} hides an executable behind a "
                             f"double extension.",
                             n[:200]))
            continue
        if any(low.endswith(e) for e in _EXECUTABLE_EXTS):
            sigs.append(_sig("attachment-executable", "high",
                             f"Attachment {n} is an executable type.",
                             n[:200]))
        elif any(low.endswith(e) for e in _ARCHIVE_EXTS):
            sigs.append(_sig("attachment-archive", "medium",
                             f"Attachment {n} is an archive: common "
                             f"malware container.",
                             n[:200]))
    return sigs


_SUSPICIOUS_PHONE_RES = [
    (re.compile(r"^\+?1-?900"), "premium-rate US number"),
    (re.compile(r"^\+?(234|233|229|225)"), "high-risk country callback prefix"),
]


# Brands scammers impersonate most. The radar compares the *registrable*
# domain of every sender/URL domain against these with a similarity score;
# close-but-not-equal => likely typosquat impersonation.
KNOWN_BRANDS = [
    "paypal", "apple", "microsoft", "amazon", "google", "netflix",
    "bankofamerica", "chase", "wellsfargo", "irs", "dhl", "fedex",
    "instagram", "facebook", "linkedin", "coinbase", "binance",
]


def _registrable(domain: str) -> str:
    """crude registrable-domain: last two labels (paypa1-secure.com)."""
    parts = (domain or "").lower().strip(".").split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else domain.lower()


def _similarity(a: str, b: str) -> float:
    """Jaccard-ish bigram similarity, cheap and dependency-free."""
    if not a or not b:
        return 0.0
    ga = {a[i:i + 2] for i in range(len(a) - 1)} or {a}
    gb = {b[i:i + 2] for i in range(len(b) - 1)} or {b}
    return len(ga & gb) / len(ga | gb)


# Legit brand-owned domains that resemble the brand itself , 
# never flag these (e.g. amazonaws.com is really Amazon).
KNOWN_GOOD = {
    "amazonaws.com", "googleapis.com", "gstatic.com", "googleusercontent.com",
    "fbcdn.net", "cdninstagram.com", "microsoftonline.com", "live.com",
    "outlook.com", "office365.com",
}


def check_brand_impersonation(sender: str, domains: list[str],
                              brand_mentions: list[str]) -> list[Signal]:
    """Flag lookalike domains that impersonate a known brand.

    Catches paypa1-secure.com (paypal), micros0ft-login.net (microsoft),
    etc.: the single most common phishing pattern. Deterministic: the
    registrable domain is split into tokens on [-_.] and each token is
    compared by bigram similarity against known brands (>= 0.40 flags).
    Exact brand matches and known-good brand infrastructure are excluded.
    """
    out: list[Signal] = []
    seen: set[str] = set()
    cands = list(dict.fromkeys(
        [_registrable(d) for d in (domains or []) if d]))
    m = re.search(r"@([\w.-]+)", sender or "")
    if m:
        cands.append(_registrable(m.group(1)))
    for dom in cands:
        if not dom or dom in seen or dom in KNOWN_GOOD:
            continue
        seen.add(dom)
        # The brand's own domain (or its subdomains) is never impersonation.
        if any(dom == f"{b}.com" or dom.endswith(f".{b}.com")
               for b in KNOWN_BRANDS):
            continue
        tokens = re.split(r"[-_.]", dom.split(".")[0])
        best: tuple[str, float] | None = None
        for tok in tokens:
            if len(tok) < 4:
                continue
            for brand in KNOWN_BRANDS:
                # NOTE: a token exactly equal to the brand still flags here
                # (e.g. apple-support.net): the brand-domain exclusion above
                # already cleared the legitimate cases.
                sim = _similarity(tok, brand)
                if sim >= 0.40 and (best is None or sim > best[1]):
                    best = (brand, sim)
        if best:
            brand, sim = best
            mentioned = brand in [b.lower() for b in (brand_mentions or [])]
            out.append(_sig(
                "brand-impersonation", "high",
                f"Domain {dom} looks like a typosquat of {brand} "
                f"(similarity {sim:.2f})"
                + (" and the brand is named in the message" if mentioned
                   else ""),
                dom))
    return out


_WEBMAIL = {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com",
            "yahoo.com", "icloud.com", "aol.com", "proton.me", "protonmail.com", "gmx.com"}
_EXEC_TITLE = re.compile(r"\b(ceo|cfo|coo|cto|president|director|managing partner|"
                         r"chairman|founder)\b", re.IGNORECASE)
_GIFT_CARD = re.compile(r"\b(buy|purchase|get|pick up|grab|send|need)\b[^.\n]{0,60}"
                        r"gift\s?cards?", re.IGNORECASE)
_CARD_CODES = re.compile(r"(codes?|scratch|photos? of)", re.IGNORECASE)
_SECRECY = re.compile(r"(keep (this|it) (between us|confidential|quiet)|don'?t (tell|mention)|"
                      r"confidential|surprise|discreet)", re.IGNORECASE)
_PAYMENT_CHANGE = re.compile(r"(update|change)d? (our |the |my )?(bank|banking|payment|wire) "
                             r"(details|information|account)|new (bank|account) details|"
                             r"wire transfer", re.IGNORECASE)


def check_bec(sender: str, body: str) -> list[Signal]:
    """Business-email-compromise patterns: the fraud lives in the words, not the links."""
    sigs = []
    m = re.match(r"\s*\"?(.*?)\"?\s*<([^>]+)>", sender or "")
    if m and _EXEC_TITLE.search(m.group(1)):
        dom = m.group(2).split("@")[-1].lower()
        if dom in _WEBMAIL:
            sigs.append(_sig("executive-on-webmail", "high",
                             f"Sender claims an executive title but writes from free webmail "
                             f"({dom}).", sender[:200]))
    gm = _GIFT_CARD.search(body or "")
    if gm and _CARD_CODES.search(body or ""):
        sigs.append(_sig("gift-card-request", "high",
                         "Asks for gift cards and their codes: a payment method scammers use "
                         "because it is untraceable.", gm.group(0)))
    pm = _PAYMENT_CHANGE.search(body or "")
    if pm:
        sigs.append(_sig("payment-change-request", "medium",
                         "Asks to change payment or bank details, a classic invoice-fraud move.",
                         pm.group(0)))
    sm = _SECRECY.search(body or "")
    if sm and (gm or pm):
        sigs.append(_sig("secrecy-pressure", "medium",
                         "Pairs a money request with secrecy, cutting you off from checking "
                         "with anyone.", sm.group(0)))
    return sigs


def check_phone_numbers(phones: list[str]) -> list[Signal]:
    sigs = []
    for p in phones or []:
        digits = re.sub(r"\D", "", p)
        for rx, why in _SUSPICIOUS_PHONE_RES:
            if rx.search(p.replace(" ", "")):
                sigs.append(_sig("suspicious-phone", "medium",
                                 f"Callback number {p} matches {why}.",
                                 p[:200]))
                break
        else:
            if len(digits) > 15 or (digits and len(digits) < 7):
                sigs.append(_sig("odd-phone-format", "low",
                                 f"Phone number {p} has an unusual digit "
                                 f"count.",
                                 p[:200]))
    return sigs


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def analyze_signals(raw_body: str = "", headers: str = "", html: str = "",
                    triage: dict | None = None) -> SignalReport:
    """Run every deterministic check. Never raises: a broken check is a
    missing signal, not a crashed pipeline."""
    t = triage or {}
    checks = [
        lambda: check_auth_results(headers),
        lambda: check_from_replyto(t.get("sender", ""), t.get("reply_to", "")),
        lambda: check_display_name_spoof(t.get("sender", "")),
        lambda: check_sender_link_mismatch(t.get("sender", ""),
                                           t.get("urls", [])),
        lambda: check_url_display_mismatch(html),
        lambda: check_punycode(t.get("domains", [])),
        lambda: check_homoglyph(t.get("domains", []),
                                t.get("brand_mentions", [])),
        lambda: check_ip_literal_url(t.get("urls", [])),
        lambda: check_url_shortener(t.get("urls", [])),
        lambda: check_suspicious_tld(t.get("domains", [])),
        lambda: check_encoded_url_tricks(t.get("urls", [])),
        lambda: check_attachments(t.get("attachment_names", [])),
        lambda: check_phone_numbers(t.get("phone_numbers", [])),
        lambda: check_brand_impersonation(t.get("sender", ""),
                                          t.get("domains", []),
                                          t.get("brand_mentions", [])),
        lambda: check_bec(t.get("sender", ""), raw_body),
    ]
    sigs: list[Signal] = []
    for c in checks:
        try:
            sigs.extend(c())
        except Exception:
            continue  # a broken check is a missing signal
    # dedup by (name, evidence)
    seen, out = set(), []
    for s in sigs:
        key = (s.name, s.evidence)
        if key not in seen:
            seen.add(key)
            out.append(s)
    return SignalReport(signals=out)


# ---------------------------------------------------------------------------
# pipeline stage
# ---------------------------------------------------------------------------

async def run(ctx):
    from .context import StageResult

    e = ctx.email
    t = ctx.results.get("triage")
    triage = t.__dict__ if t is not None else {}
    report = analyze_signals(e.text, e.headers, e.html, triage)
    flagged = [s for s in report.signals if s.severity != "info"]
    summary = (f"{len(flagged)} signal(s), {len(report.high)} high"
               if flagged else "no deterministic red flags")
    return StageResult(report, summary)
