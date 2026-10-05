#!/usr/bin/env python3
"""Verify the Momen MCP setup end to end (up to the auth gate).

Checks:
  1. node/npx available
  2. momen-mcp package resolves
  3. MCP server starts and answers initialize
  4. tools/list returns the expected tool surface
  5. auth status (WHOAMI) — reports authenticated or not; not-a-failure,
     the user completes login separately (see README.md)

Exit 0 when the plumbing is healthy. Exit 2 on setup failure.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mcp_client import MCPClient, MCPError

MOMEN_PKG = "momen-mcp@2.7.13"
EXPECTED_TOOLS = {"auth", "get_projects", "set_current_project",
                  "project_inspect", "schema_session", "sync_backend"}


def check(label, ok, detail=""):
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {label}" + (f" — {detail}" if detail else ""))
    return ok


def main():
    healthy = True

    healthy &= check("node on PATH", shutil.which("node") is not None)
    healthy &= check("npx on PATH", shutil.which("npx") is not None)

    r = subprocess.run(["npm", "view", "momen-mcp", "version"],
                       capture_output=True, text=True, timeout=30)
    healthy &= check("momen-mcp published", r.returncode == 0,
                     r.stdout.strip() or r.stderr.strip()[:80])

    c = None
    try:
        c = MCPClient(["npx", "-y", MOMEN_PKG, "mcp", "--no-daemon"])
        init = c.initialize()
        srv = init.get("result", {}).get("serverInfo", {})
        healthy &= check("MCP initialize",
                         srv.get("name") == "momen-mcp",
                         f"{srv.get('name')} v{srv.get('version')}")
        c.notify("notifications/initialized")

        tools = c.tools_list()["result"]["tools"]
        names = {t["name"] for t in tools}
        missing = EXPECTED_TOOLS - names
        healthy &= check("tool surface", not missing,
                         f"{len(names)} tools" +
                         (f"; missing {sorted(missing)}" if missing else ""))

        try:
            who = c.tool_call("auth", {"op": "WHOAMI"}, timeout=60)
            text = who["result"]["content"][0]["text"]
            authed = "not authenticated" not in text.lower()
            check("Momen auth", True,
                  "authenticated" if authed
                  else "not authenticated yet — run auth_token.py with your token")
        except MCPError as e:
            check("Momen auth", True, f"status unknown: {e}")
    except Exception as e:
        healthy &= check("MCP server", False, f"{type(e).__name__}: {e}")
    finally:
        if c:
            c.close()

    print("\nSetup " + ("OK — plumbing healthy." if healthy else "FAILED."))
    return 0 if healthy else 2


if __name__ == "__main__":
    sys.exit(main())
