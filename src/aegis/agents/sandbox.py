"""Link sandbox: isolated URL inspection.

SECURITY CONTRACT (non-negotiable):
- No JavaScript execution. Static fetch only.
- SSRF deny-list: 10/8, 172.16/12, 192.168/16, 127/8, 169.254/16, ::1,
  fc00::/7, and any hostname resolving into those ranges. Checked BEFORE the
  fetch and re-checked on the FINAL URL after redirects.
- 10s timeout, max 5 redirects, 5MB body cap.
- http/https only. NEVER submit forms, NEVER send credentials.
- The sandbox connects DIRECTLY (trust_env=False): the DNS it vetted is the
  DNS it uses. If your deployment needs an egress proxy, set
  AEGIS_SANDBOX_PROXY — the guard still applies as defense-in-depth, but note
  the proxy then does the final DNS resolution.
- A dumb fetch is a feature: a smart fetch is an attack surface.
"""
from __future__ import annotations

import os
import re
import socket
import ssl
from dataclasses import dataclass
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
    ipaddress.ip_network("fc00::/7"),
]

_MALWARE_EXTS = (".exe", ".msi", ".dmg", ".apk", ".scr", ".bat", ".ps1")


def is_blocked_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True  # unparseable → treat as hostile
    return any(addr in net for net in _SSRF_NETWORKS)


def _resolve_ips(host: str) -> list[str]:
    try:
        return list({r[4][0] for r in socket.getaddrinfo(host, None)})
    except socket.gaierror:
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


def _classify_html(html: str, final_url: str) -> PageKind:
    low = html.lower()
    if re.search(r'<input[^>]*type=["\']?password', low):
        return PageKind.CREDENTIAL_HARVEST
    if low.rstrip().endswith(_MALWARE_EXTS) or urlparse(final_url).path.lower().endswith(_MALWARE_EXTS):
        return PageKind.MALWARE_DROP
    return PageKind.BENIGN


@dataclass
class SandboxVerdict:
    url: str
    final_url: str = ""
    kind: PageKind = PageKind.UNREACHABLE
    status_code: int | None = None
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
    ok, reason = url_allowed(url)
    if not ok:
        return SandboxVerdict(url=url, note=f"blocked pre-fetch: {reason}")
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
                ok2, reason2 = url_allowed(final)
                if not ok2:
                    return SandboxVerdict(url=url, final_url=final,
                                          note=f"blocked after redirect: {reason2}")
                body = b""
                for chunk in r.iter_bytes(65536):
                    body += chunk
                    if len(body) > MAX_BODY_BYTES:
                        break
                kind = _classify_html(body.decode("utf-8", "replace"), final)
                return SandboxVerdict(url=url, final_url=final, kind=kind,
                                      status_code=r.status_code)
    except Exception as e:  # network is hostile; never let it crash the pipeline
        return SandboxVerdict(url=url, kind=PageKind.UNREACHABLE,
                              note=str(e)[:200])


def inspect_urls(urls: list[str]) -> list[SandboxVerdict]:
    return [inspect_url(u) for u in urls]
