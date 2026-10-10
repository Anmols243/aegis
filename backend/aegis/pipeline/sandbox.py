"""Stage 5: link sandbox. A deliberately dumb, isolated fetch of each URL.

No JavaScript, no form submission, no cookies, bounded size and time.

SSRF defence (every URL in an email is attacker-controlled):
- Only http/https.
- The hostname is resolved once; EVERY resolved address must be public
  (`is_global`), which rejects loopback, private, link-local, CGNAT
  (100.64/10), 0.0.0.0, multicast, and IPv4 addresses smuggled inside IPv6
  (IPv4-mapped, 6to4, NAT64, Teredo).
- The connection goes to the exact IP that was checked (Host header and TLS
  SNI carry the name), so a DNS answer cannot change between check and
  connect (closes DNS rebinding).
- Redirects are followed manually and every hop goes through the same check,
  so a public URL cannot bounce the fetcher into an internal address.
"""
from __future__ import annotations

import asyncio
import html as html_lib
import ipaddress
import re
import socket
import time
from dataclasses import asdict, dataclass, field
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from .context import PipelineContext, Skip, StageResult

MAX_URLS = 5
MAX_REDIRECTS = 5
MAX_BODY_BYTES = 512 * 1024
DNS_TIMEOUT_S = 4.0
FETCH_TIMEOUT_S = 8.0
_REDIRECTS = {301, 302, 303, 307, 308}
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_MALWARE_EXTS = (".exe", ".msi", ".dmg", ".apk", ".scr", ".bat", ".ps1", ".js", ".vbs",
                 ".jar", ".iso", ".lnk", ".hta", ".zip", ".rar", ".7z")

RISK = {"credential-harvest": 1.0, "malware-drop": 0.7, "blocked": 0.5,
        "unreachable": 0.3, "benign": 0.1}


def embedded_ipv4(ip: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    """The IPv4 address an IPv6 address wraps (mapped, 6to4, NAT64), if any.

    Checked explicitly instead of trusting `is_global` on the IPv6 form: before
    Python 3.13 an IPv4-mapped loopback such as ::ffff:127.0.0.1 reported global."""
    if ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    if ip.sixtofour is not None:
        return ip.sixtofour
    if ip in _NAT64:
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return None


def is_public_ip(value: str) -> bool:
    """True only for globally routable unicast addresses."""
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.teredo is not None:
            return False
        ip = embedded_ipv4(ip) or ip
    return bool(ip.is_global) and not ip.is_multicast


async def resolve(host: str, port: int) -> list[str]:
    """Resolve to unique addresses with a hard timeout. [] = failure."""
    try:
        ipaddress.ip_address(host)
        return [host]
    except ValueError:
        pass
    loop = asyncio.get_running_loop()
    try:
        infos = await asyncio.wait_for(
            loop.getaddrinfo(host, port, type=socket.SOCK_STREAM), DNS_TIMEOUT_S)
    except (OSError, asyncio.TimeoutError, UnicodeError):
        return []
    return list(dict.fromkeys(info[4][0] for info in infos))


@dataclass
class LinkVerdict:
    url: str
    final_url: str = ""
    kind: str = "unreachable"
    status_code: int | None = None
    redirect_chain: list[str] = field(default_factory=list)
    page_title: str = ""
    has_password_form: bool = False
    has_login_form: bool = False
    download_detected: bool = False
    failure_reason: str = ""
    duration_s: float = 0.0

    @property
    def risk(self) -> float:
        return RISK[self.kind]

    def public(self) -> dict:
        d = asdict(self)
        d["risk"] = self.risk
        return d


_TAG = re.compile(r"<(input|form|a)\b([^<>]*)")   # stops at the next < or >: linear
_HREF = re.compile(r"href=[\"']?([^\"'\s]*)")
_LOGIN_WORDS = re.compile(r"log\s?in|sign[\s-]?in|password|verify")
_FORM_ACTION = re.compile(r'''\baction\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))''')
_MICROSOFT_LOGIN_HOSTS = {"login.microsoftonline.com", "login.live.com"}


def _microsoft_login_url(url: str) -> bool:
    """A known HTTPS login endpoint is not itself credential theft.

    This says nothing about the email, tenant or app requesting access.
    """
    try:
        p = urlsplit(url)
        return (p.scheme == "https" and p.hostname in _MICROSOFT_LOGIN_HOSTS
                and p.port in (None, 443) and not p.username and not p.password)
    except ValueError:
        return False


def classify_html(html: str, final_url: str) -> dict:
    # Attacker-controlled page: every scan here must stay linear in the body size,
    # since this runs on the event loop (a backtracking regex would stall the server).
    low = html.lower()
    has_password, first_form_end, download = False, -1, False
    login_targets = _microsoft_login_url(final_url)
    for m in _TAG.finditer(low):
        tag, attrs = m.group(1), m.group(2)
        if tag == "input":
            has_password = has_password or bool(re.search(r"type=[\"']?password", attrs))
        elif tag == "form":
            if first_form_end < 0:
                first_form_end = m.end()
            action = _FORM_ACTION.search(attrs)
            target = next((v for v in action.groups() if v is not None), "") if action else ""
            login_targets = login_targets and _microsoft_login_url(
                urljoin(final_url, html_lib.unescape(target)))
        elif not download:
            download = any(v.endswith(_MALWARE_EXTS) for v in _HREF.findall(attrs))
    has_login = has_password or (first_form_end >= 0
                                 and bool(_LOGIN_WORDS.search(low, first_form_end)))
    title = ""
    start = low.find("<title")
    if start >= 0:
        gt = low.find(">", start)
        end = low.find("</title>", gt) if gt >= 0 else -1
        if end >= 0:
            src = html if len(html) == len(low) else low
            title = re.sub(r"\s+", " ", src[gt + 1:end]).strip()[:160]
    path = urlsplit(final_url).path.lower()
    if has_password and not login_targets:
        kind = "credential-harvest"
    elif path.endswith(_MALWARE_EXTS) or download:
        kind = "malware-drop"
    else:
        kind = "benign"
    return {"kind": kind, "page_title": title, "has_password_form": has_password,
            "has_login_form": has_login, "download_detected": download}


async def _open(client: httpx.AsyncClient, url: str) -> tuple[httpx.Response | None, str]:
    """Open one hop pinned to a vetted IP. Returns (response, block_reason)."""
    p = urlsplit(url)
    if p.scheme not in ("http", "https"):
        return None, f"blocked scheme {p.scheme or '(none)'}"
    host = (p.hostname or "").rstrip(".")
    if not host:
        return None, "no hostname"
    if p.username or p.password:
        return None, "credentials embedded in URL"
    try:
        ascii_host = host.encode("idna").decode("ascii")
    except UnicodeError:
        ascii_host = host
    port = p.port or (443 if p.scheme == "https" else 80)
    ips = await resolve(ascii_host, port)
    if not ips:
        return None, "unresolvable"
    private = [ip for ip in ips if not is_public_ip(ip)]
    if private:
        return None, f"resolves to non-public address {private[0]}"
    ip = ips[0]
    netloc = (f"[{ip}]" if ":" in ip else ip) + (f":{p.port}" if p.port else "")
    target = urlunsplit((p.scheme, netloc, p.path or "/", p.query, ""))
    host_header = ascii_host + (f":{p.port}" if p.port else "")
    ext = {"sni_hostname": ascii_host} if p.scheme == "https" else {}
    req = client.build_request("GET", target, extensions=ext,
                               headers={"Host": host_header,
                                        "User-Agent": "AEGIS-sandbox/2.0 (+scam analysis)",
                                        "Accept": "text/html,*/*;q=0.5"})
    return await client.send(req, stream=True), ""


async def inspect_url(url: str) -> LinkVerdict:
    t0 = time.monotonic()
    v = LinkVerdict(url=url)
    current = url
    try:
        async with httpx.AsyncClient(follow_redirects=False, trust_env=False,
                                     timeout=FETCH_TIMEOUT_S, verify=True) as client:
            for hop in range(MAX_REDIRECTS + 1):
                resp, reason = await _open(client, current)
                if resp is None:
                    v.kind = "unreachable" if reason == "unresolvable" else "blocked"
                    v.failure_reason = reason if hop == 0 else f"after redirect: {reason}"
                    v.final_url = current
                    return v
                try:
                    v.status_code = resp.status_code
                    location = resp.headers.get("location")
                    if resp.status_code in _REDIRECTS and location:
                        v.redirect_chain.append(current)
                        current = urljoin(current, location)
                        continue
                    body = b""
                    async for chunk in resp.aiter_bytes():
                        body += chunk
                        if len(body) >= MAX_BODY_BYTES:
                            break
                finally:
                    await resp.aclose()
                v.final_url = current
                info = classify_html(body.decode("utf-8", "replace"), current)
                for k, val in info.items():
                    setattr(v, k, val)
                return v
            v.kind, v.failure_reason, v.final_url = "blocked", "too many redirects", current
            return v
    except Exception as e:  # noqa: BLE001 - the network is hostile; never crash the pipeline
        v.kind = "unreachable"
        v.failure_reason = f"{type(e).__name__}: {str(e)[:160]}"
        v.final_url = v.final_url or current
        return v
    finally:
        v.duration_s = round(time.monotonic() - t0, 2)


async def run(ctx: PipelineContext) -> StageResult:
    if not ctx.settings.sandbox_enabled:
        raise Skip("sandbox disabled")
    triage = ctx.results.get("triage")
    urls = list(dict.fromkeys(triage.urls))[:MAX_URLS] if triage else []
    if not urls:
        raise Skip("no links in the email")
    verdicts = await asyncio.gather(*(inspect_url(u) for u in urls))
    counts: dict[str, int] = {}
    for v in verdicts:
        counts[v.kind] = counts.get(v.kind, 0) + 1
    detail = ", ".join(f"{n} {k}" for k, n in sorted(counts.items()))
    return StageResult(list(verdicts), f"{len(verdicts)} link(s): {detail}")
