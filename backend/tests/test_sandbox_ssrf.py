"""SSRF hardening of the link sandbox, against a real local HTTP server."""
from __future__ import annotations

import http.server
import threading

import pytest

from aegis.pipeline import sandbox


@pytest.mark.parametrize("ip,public", [
    ("8.8.8.8", True),
    ("2606:4700:4700::1111", True),
    ("127.0.0.1", False),
    ("0.0.0.0", False),
    ("10.0.0.1", False),
    ("172.16.5.4", False),
    ("192.168.1.1", False),
    ("169.254.169.254", False),        # cloud metadata
    ("100.64.0.1", False),             # carrier-grade NAT
    ("::1", False),
    ("fe80::1", False),
    ("fc00::1", False),
    ("::ffff:127.0.0.1", False),       # IPv4-mapped loopback
    ("::ffff:169.254.169.254", False),  # IPv4-mapped metadata
    ("2002:7f00:1::", False),          # 6to4 wrapping 127.0.0.1
    ("64:ff9b::7f00:1", False),        # NAT64 wrapping 127.0.0.1
    ("224.0.0.1", False),              # multicast
    ("not-an-ip", False),
])
def test_is_public_ip(ip, public):
    assert sandbox.is_public_ip(ip) is public


class _Handler(http.server.BaseHTTPRequestHandler):
    seen_hosts: list[str] = []

    def do_GET(self):  # noqa: N802
        _Handler.seen_hosts.append(self.headers.get("Host", ""))
        if self.path.startswith("/redirect-internal"):
            self.send_response(302)
            self.send_header("Location", "http://10.1.2.3/admin")
            self.end_headers()
            return
        body = b"<html><title>Sign in</title><form><input type='password'></form></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture
def local_server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    _Handler.seen_hosts.clear()
    yield srv.server_address[1]
    srv.shutdown()


async def test_private_destination_blocked_without_request(local_server):
    v = await sandbox.inspect_url(f"http://127.0.0.1:{local_server}/")
    assert v.kind == "blocked"
    assert "non-public" in v.failure_reason
    assert _Handler.seen_hosts == []       # nothing was ever sent


async def test_redirect_hop_into_private_network_blocked(local_server, monkeypatch):
    # Treat the test server as "public" so the first hop is allowed.
    monkeypatch.setattr(sandbox, "is_public_ip", lambda ip: ip == "127.0.0.1")
    v = await sandbox.inspect_url(f"http://127.0.0.1:{local_server}/redirect-internal")
    assert v.kind == "blocked"
    assert v.failure_reason.startswith("after redirect")
    assert v.redirect_chain and "10.1.2.3" in v.final_url


async def test_connection_pinned_to_checked_ip(local_server, monkeypatch):
    """The fetch connects to the IP that passed the check, sending the original
    hostname only in the Host header (no second DNS lookup to rebind)."""
    async def resolve(host, port):
        return ["127.0.0.1"] if host == "phish.test" else []
    monkeypatch.setattr(sandbox, "resolve", resolve)
    monkeypatch.setattr(sandbox, "is_public_ip", lambda ip: ip == "127.0.0.1")
    v = await sandbox.inspect_url(f"http://phish.test:{local_server}/login")
    assert v.kind == "credential-harvest"
    assert v.has_password_form and v.page_title == "Sign in"
    assert _Handler.seen_hosts == [f"phish.test:{local_server}"]


async def test_non_http_schemes_and_userinfo_blocked():
    assert (await sandbox.inspect_url("file:///etc/passwd")).kind == "blocked"
    assert (await sandbox.inspect_url("ftp://example.com/x")).kind == "blocked"
    v = await sandbox.inspect_url("http://paypal.com@203.0.113.9/")
    assert v.kind == "blocked" and "credentials" in v.failure_reason


@pytest.mark.parametrize("v6,v4", [
    ("::ffff:127.0.0.1", "127.0.0.1"),
    ("2002:7f00:1::", "127.0.0.1"),
    ("64:ff9b::a9fe:a9fe", "169.254.169.254"),
    ("2606:4700:4700::1111", None),
])
def test_embedded_ipv4_is_unwrapped(v6, v4):
    """Independent of the Python version's own is_global behaviour."""
    import ipaddress
    got = sandbox.embedded_ipv4(ipaddress.IPv6Address(v6))
    assert (str(got) if got else None) == v4
