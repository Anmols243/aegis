"""Link sandbox: isolated URL inspection.

SECURITY CONTRACT (non-negotiable):
- No JavaScript execution. Static fetch only.
- SSRF deny-list: 10/8, 172.16/12, 192.168/16, 127/8, 169.254/16,
  ::1/128, fe80::/10 (link-local), fc00::/7, and any hostname resolving
  into those ranges. Checked BEFORE the fetch and re-checked on the FINAL
  URL after redirects.
- DNS is vetted pre-fetch, but the HTTP client performs its own resolution
  at connect time — a hostile DNS can answer differently between the check
  and the fetch (TOCTOU / DNS rebinding). The pre-check is a cheap filter,
  not a guarantee; the redirect re-check and scheme/IP guards are the
  defense-in-depth that remains. Documented honestly, not oversold.
- 10s timeout, max 5 redirects, 5MB body cap, bounded DNS lookup time.
- http/https only. NEVER submit forms, NEVER send credentials.
- The sandbox connects DIRECTLY (trust_env=False). If your deployment needs
  an egress proxy, set AEGIS_SANDBOX_PROXY — the guard still applies as
  defense-in-depth, but note the proxy then does the final DNS resolution.
- A dumb fetch is a feature: a smart fetch is an attack surface.
"""
from __future__ import annotations

import os
import re
import socket
import ssl
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse

import httpx

import ipaddress

MAX_BODY_BYTES = 5 * 1024 * 1024


class PageKind(str, Enum):
    CREDENTIAL_HARVEST = "credential-harvest"
    MALWARE_DROP = "malware-drop"
    BENIGN = "benign"
    UNREACHABLE = "unreachable"


_SSRF_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fe80::/10"),   # IPv6 link-local
    ipaddress.ip_network("fc00::/7"),
]

_DNS_TIMEOUT_S = 5.0  # bound the pre-fetch resolution; a stall fails closed

_MALWARE_EXTS = (".exe", ".msi", ".dmg", ".apk", ".scr", ".bat", ".ps1")


def is_blocked_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True  # unparseable → treat as hostile
    return any(addr in net for net in _SSRF_NETWORKS)


def _resolve_ips(host: str) -> list[str]:
    """Resolve a hostname with a hard timeout. Empty list = fail closed."""
    import concurrent.futures
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(socket.getaddrinfo, host, None)
            results = fut.result(timeout=_DNS_TIMEOUT_S)
        return list({r[4][0] for r in results})
    except Exception:
        return []


def url_allowed(url: str) -> tuple[bool, str]:
    """(allowed, reason). Pure function — unit-testable without network."""
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        return False, f"blocked scheme: {p.scheme or '(none)'}"
    if not p.hostname:
        return False, "no hostname"
    ips = _resolve_ips(p.hostname)
    if not ips:
        return False, "DNS resolution failed"
    for ip in ips:
        if is_blocked_ip(ip):
            return False, f"resolves to blocked IP {ip}"
    return True, ""


def _classify_html(html: str, final_url: str) -> tuple[PageKind, dict]:
    """Classify a fetched page. Returns (kind, observables).

    Observables come from dumb regexes over static HTML — no JS execution,
    no form submission, no credentials. A dumb fetch is a feature.
    """
    low = html.lower()
    has_password = bool(re.search(r'<input[^>]*type=["\']?password', low))
    has_login = has_password or bool(re.search(
        r"<form[^>]*>.*?(login|sign[\s-]?in|password)", low, re.DOTALL))
    title_m = re.search(r"<title[^>]*>(.*?)</title>", low, re.DOTALL)
    title = (re.sub(r"\s+", " ", title_m.group(1)).strip()[:120]
             if title_m else "")
    ext_pat = "|".join(e.lstrip(".") for e in _MALWARE_EXTS)
    download = low.rstrip().endswith(_MALWARE_EXTS) or bool(
        re.search(r'<a[^>]+href=["\']?[^"\']*\.' + ext_pat + r'["\']?', low))
    if has_password:
        kind = PageKind.CREDENTIAL_HARVEST
    elif (urlparse(final_url).path.lower().endswith(_MALWARE_EXTS)
          or download):
        kind = PageKind.MALWARE_DROP
    else:
        kind = PageKind.BENIGN
    return kind, {
        "has_password_form": has_password,
        "has_login_form": has_login,
        "page_title": title,
        "download_detected": download,
    }


@dataclass
class SandboxVerdict:
    url: str
    final_url: str = ""
    kind: PageKind = PageKind.UNREACHABLE
    status_code: int | None = None
    content_type: str = ""
    hostname: str = ""
    page_title: str = ""
    redirect_chain: list[str] = field(default_factory=list)
    has_password_form: bool = False
    has_login_form: bool = False
    download_detected: bool = False
    fetch_duration_s: float = 0.0
    failure_reason: str = ""
    note: str = ""

    @property
    def risk(self) -> float:
        return {
            PageKind.CREDENTIAL_HARVEST: 1.0,
            PageKind.MALWARE_DROP: 0.6,
            PageKind.UNREACHABLE: 0.3,
            PageKind.BENIGN: 0.1,
        }[self.kind]


def inspect_url(url: str) -> SandboxVerdict:
    import time
    t0 = time.time()
    try:
        hostname = (urlparse(url).hostname or "").lower()
    except Exception:
        hostname = ""
    ok, reason = url_allowed(url)
    if not ok:
        return SandboxVerdict(url=url, hostname=hostname,
                              failure_reason=f"blocked pre-fetch: {reason}",
                              note=f"blocked pre-fetch: {reason}")
    proxy = os.environ.get("AEGIS_SANDBOX_PROXY") or None
    ca_bundle = os.environ.get("AEGIS_SANDBOX_CA_BUNDLE")
    verify: ssl.SSLContext | bool = True
    if ca_bundle:  # e.g. corp/TLS-intercepting egress proxies
        verify = ssl.create_default_context(cafile=ca_bundle)
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True,
                          max_redirects=5, trust_env=False,
                          proxy=proxy, verify=verify) as c:
            with c.stream("GET", url,
                          headers={"User-Agent": "AEGIS-sandbox/1.0"}) as r:
                final = str(r.url)
                chain = [str(h.url) for h in getattr(r, "history", [])]
                ok2, reason2 = url_allowed(final)
                if not ok2:
                    return SandboxVerdict(
                        url=url, final_url=final, hostname=hostname,
                        status_code=r.status_code, redirect_chain=chain,
                        fetch_duration_s=round(time.time() - t0, 2),
                        failure_reason=f"blocked after redirect: {reason2}",
                        note=f"blocked after redirect: {reason2}")
                ctype = r.headers.get("content-type", "").split(";")[0].strip()
                body = b""
                for chunk in r.iter_bytes(65536):
                    body += chunk
                    if len(body) > MAX_BODY_BYTES:
                        break
                kind, obs = _classify_html(body.decode("utf-8", "replace"),
                                           final)
                return SandboxVerdict(
                    url=url, final_url=final, kind=kind,
                    status_code=r.status_code, content_type=ctype,
                    hostname=hostname, page_title=obs["page_title"],
                    redirect_chain=chain,
                    has_password_form=obs["has_password_form"],
                    has_login_form=obs["has_login_form"],
                    download_detected=obs["download_detected"],
                    fetch_duration_s=round(time.time() - t0, 2))
    except Exception as e:  # network is hostile; never let it crash the pipeline
        return SandboxVerdict(url=url, hostname=hostname,
                              kind=PageKind.UNREACHABLE,
                              failure_reason=str(e)[:200],
                              fetch_duration_s=round(time.time() - t0, 2),
                              note=str(e)[:200])


def inspect_urls(urls: list[str]) -> list[SandboxVerdict]:
    return [inspect_url(u) for u in urls]
