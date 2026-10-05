#!/usr/bin/env python3
"""Store the user's Momen access token for momen-mcp and verify it.

The token comes from running `npx -y momen-mcp@2.7.13 login` on the user's
own machine, then copying the `access_token` value out of
~/.momen-mcp/credentials.json.

Usage:
    python3 auth_token.py            # prompts securely (no echo)
    echo "$TOKEN" | python3 auth_token.py --stdin

Writes ~/.momen-mcp/credentials.json (mode 0600) in the exact shape the
momen-mcp CredentialStore expects, then verifies with auth WHOAMI.
The token is never printed.
"""
import base64
import getpass
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mcp_client import MCPClient, MCPError

CRED_PATH = Path.home() / ".momen-mcp" / "credentials.json"
MOMEN_PKG = "momen-mcp@2.7.13"


def looks_like_jwt(token: str) -> bool:
    parts = token.split(".")
    if len(parts) != 3:
        return False
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        json.loads(base64.urlsafe_b64decode(payload))
        return True
    except Exception:
        return False


def read_token() -> str:
    if "--stdin" in sys.argv:
        token = sys.stdin.read().strip()
    else:
        token = getpass.getpass("Paste your Momen access_token: ").strip()
    return token


def main():
    token = read_token()
    if not token:
        print("No token given — nothing written.", file=sys.stderr)
        return 2
    if not looks_like_jwt(token):
        print("That doesn't look like a JWT access token — nothing written.",
              file=sys.stderr)
        return 2

    CRED_PATH.parent.mkdir(parents=True, exist_ok=True)
    CRED_PATH.write_text(json.dumps({
        "access_token": token,
        "token_type": "Bearer",
        "savedAt": datetime.now(timezone.utc).isoformat(),
    }, indent=2))
    os.chmod(CRED_PATH, 0o600)
    print(f"Wrote {CRED_PATH} (0600). Verifying…")

    c = MCPClient(["npx", "-y", MOMEN_PKG, "mcp", "--no-daemon"])
    try:
        c.initialize()
        c.notify("notifications/initialized")
        who = c.tool_call("auth", {"op": "WHOAMI"}, timeout=60)
        text = who["result"]["content"][0]["text"]
        if "not authenticated" in text.lower():
            print("Token was NOT accepted by Momen. It may be expired — "
                  "re-run `momen-mcp login` on your machine and try again.")
            return 3
        print("Authenticated with Momen. WHOAMI:")
        print(text[:800])
        return 0
    except MCPError as e:
        print(f"Verification failed: {e}")
        return 3
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())
