#!/usr/bin/env python3
"""Minimal localtunnel client that works through an HTTP CONNECT proxy.

Protocol (from localtunnel's own client source):
  1. GET https://localtunnel.me/<subdomain> (or ?new) -> {id, port, url, max_conn_count}
  2. Open up to max_conn raw TCP connections to localtunnel.me:port
     (via proxy CONNECT). The port identifies the tunnel server-side.
  3. Each connection is a dumb byte pipe: server sends an HTTP request,
     we forward it to localhost:PORT and pipe the response back. One
     request/response per connection, then reconnect.

Usage: python3 lt_tunnel.py [local_port] [subdomain]
Prints the public URL on stdout. Runs until killed.
"""
import base64
import json
import os
import select
import socket
import sys
import threading
import time
import urllib.parse
import urllib.request

LOCAL_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
SUBDOMAIN = sys.argv[2] if len(sys.argv) > 2 else None


def _proxy_parts():
    p = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY", "")
    u = urllib.parse.urlparse(p)
    auth = None
    if u.username:
        auth = base64.b64encode(
            f"{urllib.parse.unquote(u.username)}:"
            f"{urllib.parse.unquote(u.password or '')}".encode()
        ).decode()
    return u.hostname, u.port or 3128, auth


def connect_via_proxy(host, port, timeout=20):
    phost, pport, auth = _proxy_parts()
    s = socket.create_connection((phost, pport), timeout=timeout)
    req = (f"CONNECT {host}:{port} HTTP/1.1\r\n"
           f"Host: {host}:{port}\r\n")
    if auth:
        req += f"Proxy-Authorization: Basic {auth}\r\n"
    req += "\r\n"
    s.sendall(req.encode())
    resp = b""
    while b"\r\n\r\n" not in resp:
        chunk = s.recv(4096)
        if not chunk:
            raise RuntimeError("proxy closed CONNECT")
        resp += chunk
    status = resp.split(b"\r\n", 1)[0]
    if b" 200" not in status:
        raise RuntimeError(f"CONNECT failed: {status!r}")
    return s


def pipe(a, b):
    """Bidirectional copy until EOF on either side."""
    socks = [a, b]
    try:
        while True:
            r, _, _ = select.select(socks, [], [], 60)
            if not r:
                break
            for s in r:
                data = s.recv(65536)
                if not data:
                    return
                (b if s is a else a).sendall(data)
    except OSError:
        pass


def connect_relay(host, port, timeout=20):
    """Relay connections are raw TCP. Direct egress works for the relay
    ports; the HTTP proxy refuses CONNECT to them, so try direct first
    and fall back to the proxy."""
    try:
        return socket.create_connection((host, port), timeout=timeout)
    except Exception as e:
        print(f"[tunnel] direct relay failed ({e}), trying proxy", flush=True)
        return connect_via_proxy(host, port, timeout=timeout)


def serve_one(remote_host, remote_port):
    """One tunnel connection: pipe a single request/response cycle."""
    while True:
        try:
            remote = connect_relay(remote_host, remote_port)
        except Exception as e:
            print(f"[tunnel] remote connect failed: {e}, retrying",
                  flush=True)
            time.sleep(2)
            continue
        try:
            local = socket.create_connection(("127.0.0.1", LOCAL_PORT),
                                             timeout=10)
        except OSError:
            remote.close()
            time.sleep(1)
            continue
        pipe(remote, local)
        try:
            remote.close()
        except OSError:
            pass
        try:
            local.close()
        except OSError:
            pass


def resolve_real_ip(host):
    """Local DNS is hijacked (returns a middlebox IP), so resolve via
    DNS-over-HTTPS through the proxy to get the real address."""
    req = urllib.request.Request(
        f"https://dns.google/resolve?name={host}&type=A",
        headers={"User-Agent": "aegis-lt/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.load(r)
    for a in data.get("Answer", []):
        if a.get("type") == 1:
            return a["data"]
    raise RuntimeError(f"DoH resolve failed for {host}")


def main():
    path = f"/{SUBDOMAIN}" if SUBDOMAIN else "/?new"
    req = urllib.request.Request(
        f"https://localtunnel.me{path}",
        headers={"User-Agent": "aegis-lt/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        info = json.load(r)
    url = info["url"]
    # Modern localtunnel: data connection goes back to the API host on the
    # assigned port (the port identifies the tunnel). Resolve the real IP
    # via DoH - local DNS returns a middlebox address.
    remote_host = resolve_real_ip("localtunnel.me")
    remote_port = info["port"]
    max_conn = info.get("max_conn_count") or 5
    print(f"PUBLIC_URL={url}", flush=True)
    print(f"[tunnel] {url} -> localhost:{LOCAL_PORT} "
          f"via {remote_host}:{remote_port} x{max_conn}", flush=True)

    threads = []
    for _ in range(min(max_conn, 5)):
        t = threading.Thread(target=serve_one,
                             args=(remote_host, remote_port), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
