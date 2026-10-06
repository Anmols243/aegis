"""IMAP mailbox access (sync, run in a worker thread).

Privacy and safety:
- Messages are fetched with BODY.PEEK, so AEGIS never marks mail as read.
- The only write is adding a label or flag to a message. Nothing is moved,
  deleted or sent.
- The server must resolve to a public address (same rule as the link sandbox)
  and the TLS connection is pinned to that checked IP, so a user-supplied
  "mail server" cannot be used to probe internal networks.
- Only implicit TLS on port 993 is allowed.
"""
from __future__ import annotations

import imaplib
import re
import socket
import ssl

from ..pipeline.sandbox import is_public_ip

PORT = 993
MAX_MESSAGE_BYTES = 2 * 1024 * 1024
TIMEOUT_S = 20

PROVIDERS: list[dict] = [
    {"id": "gmail", "name": "Gmail", "host": "imap.gmail.com", "port": PORT,
     "supported": True, "app_password_url": "https://myaccount.google.com/apppasswords",
     "steps": ["Turn on 2-Step Verification for your Google account.",
               "Open App passwords and create one named AEGIS.",
               "Paste the 16-character password below. Spaces are fine."]},
    {"id": "yahoo", "name": "Yahoo Mail", "host": "imap.mail.yahoo.com", "port": PORT,
     "supported": True, "app_password_url": "https://login.yahoo.com/account/security",
     "steps": ["Open Account security in your Yahoo account.",
               "Choose Generate app password, name it AEGIS.",
               "Paste the generated password below."]},
    {"id": "icloud", "name": "iCloud Mail", "host": "imap.mail.me.com", "port": PORT,
     "supported": True, "app_password_url": "https://account.apple.com/account/manage",
     "steps": ["Sign in at account.apple.com and open Sign-In and Security.",
               "Choose App-Specific Passwords and generate one named AEGIS.",
               "Use your full iCloud email address and paste the password below."]},
    {"id": "custom", "name": "Other IMAP provider", "host": None, "port": PORT,
     "supported": True, "app_password_url": None,
     "steps": ["Find your provider's IMAP server name (SSL/TLS, port 993).",
               "Create an app password if your provider offers them.",
               "Enter the server, your address and the password below."]},
    {"id": "outlook", "name": "Outlook / Hotmail", "host": "outlook.office365.com", "port": PORT,
     "supported": False, "app_password_url": None, "steps": [],
     "reason": "Microsoft no longer accepts app passwords over IMAP for Outlook.com; it needs "
               "Microsoft sign-in, which AEGIS does not support yet. Forward suspicious mail "
               "to the AEGIS inbox instead."},
]
BY_ID = {p["id"]: p for p in PROVIDERS}


class ImapError(Exception):
    """A failure with a message that is safe and useful to show the user."""


def resolve_public(host: str, port: int = PORT) -> str:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        raise ImapError("Could not find that mail server. Check the server name.") from None
    ips = list(dict.fromkeys(i[4][0] for i in infos))
    if not ips:
        raise ImapError("Could not find that mail server. Check the server name.")
    if any(not is_public_ip(ip) for ip in ips):
        raise ImapError("That mail server address is not allowed (not a public address).")
    return ips[0]


class _PinnedIMAP(imaplib.IMAP4_SSL):
    """IMAP over TLS to a pre-checked IP; the hostname is used for SNI and
    certificate verification only."""

    def __init__(self, host: str, ip: str, port: int):
        self._pinned_ip = ip
        super().__init__(host, port, ssl_context=ssl.create_default_context(), timeout=TIMEOUT_S)

    def _create_socket(self, timeout):  # noqa: D401 - imaplib hook
        sock = socket.create_connection((self._pinned_ip, self.port), timeout)
        return self.ssl_context.wrap_socket(sock, server_hostname=self.host)


def open_session(host: str, port: int, username: str, password: str) -> imaplib.IMAP4:
    if port != PORT:
        raise ImapError("Only IMAP over SSL/TLS on port 993 is supported.")
    ip = resolve_public(host, port)
    try:
        conn = _PinnedIMAP(host, ip, port)
    except (OSError, ssl.SSLError):
        raise ImapError("Could not open a secure connection to the mail server.") from None
    try:
        conn.login(username, password)
    except imaplib.IMAP4.error:
        try:
            conn.logout()
        except Exception:  # noqa: BLE001
            pass
        raise ImapError("The mail server rejected the address or app password. Use an app "
                        "password, not your normal password, and check IMAP is enabled.") from None
    return conn


def close(conn) -> None:
    try:
        conn.logout()
    except Exception:  # noqa: BLE001 - best effort
        pass


def is_gmail(conn) -> bool:
    return any("X-GM-EXT-1" in str(c).upper() for c in getattr(conn, "capabilities", ()))


def inbox_state(conn) -> tuple[int, int]:
    """(uidvalidity, uidnext) of INBOX."""
    typ, data = conn.status("INBOX", "(UIDNEXT UIDVALIDITY)")
    if typ != "OK" or not data:
        raise ImapError("Could not read the inbox.")
    text = data[0].decode() if isinstance(data[0], bytes) else str(data[0])
    nxt = re.search(r"UIDNEXT (\d+)", text)
    val = re.search(r"UIDVALIDITY (\d+)", text)
    if not nxt or not val:
        raise ImapError("The mail server did not report inbox state.")
    return int(val.group(1)), int(nxt.group(1))


def fetch_new(conn, last_uid: int, limit: int) -> list[tuple[int, bytes]]:
    """Messages with UID > last_uid, oldest first, without marking them read."""
    conn.select("INBOX", readonly=True)
    typ, data = conn.uid("search", None, f"UID {last_uid + 1}:*")
    if typ != "OK":
        return []
    uids = sorted(int(u) for u in (data[0] or b"").split() if int(u) > last_uid)[:limit]
    out = []
    for uid in uids:
        typ, sized = conn.uid("fetch", str(uid), "(RFC822.SIZE)")
        m = re.search(rb"RFC822\.SIZE (\d+)", sized[0] if sized and sized[0] else b"")
        if m and int(m.group(1)) > MAX_MESSAGE_BYTES:
            out.append((uid, b""))      # too large: skipped, but the cursor moves past it
            continue
        typ, msg = conn.uid("fetch", str(uid), "(BODY.PEEK[])")
        raw = next((part[1] for part in (msg or []) if isinstance(part, tuple)), b"")
        out.append((uid, raw))
    return out


def apply_label(conn, uid: int, label: str, gmail: bool) -> None:
    """SCAM: label + star/flag. SUSPICIOUS: label only. Never moves or deletes."""
    name = {"SCAM": "Scam", "SUSPICIOUS": "Suspicious"}[label]
    conn.select("INBOX", readonly=False)
    if gmail:
        conn.uid("store", str(uid), "+X-GM-LABELS", f'("AEGIS/{name}")')
        if label == "SCAM":
            conn.uid("store", str(uid), "+FLAGS", "(\\Flagged)")
    else:
        flags = f"(\\Flagged $AEGIS_{name})" if label == "SCAM" else f"($AEGIS_{name})"
        conn.uid("store", str(uid), "+FLAGS", flags)
