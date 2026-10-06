"""Live end-to-end test: pipeline -> verdict card -> in-thread reply.

Usage: python scripts/live_e2e.py <inbox-id> <message-id>
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from aegis import notify
from aegis.orchestrator import analyze_email

AB = os.path.expanduser("~/workspace/skills/agentboxd/bin/ab.py")


def ab(*args: str) -> dict:
    out = subprocess.run([AB, *args], capture_output=True, text=True, timeout=300)
    if out.returncode != 0:
        raise RuntimeError(f"ab.py failed: {out.stderr.strip()[:200]}")
    return json.loads(out.stdout)


def main() -> int:
    inbox_id, message_id = sys.argv[1], sys.argv[2]
    msg = ab("message", "get", message_id)
    body = msg.get("text") or msg.get("extracted_text") or ""
    print(f"[e2e] analyzing '{msg.get('subject')}' ...", flush=True)
    res = analyze_email(message_id, body, msg.get("headers") or "",
                        msg.get("html") or "", notify.message_scores(msg))
    print(f"[e2e] verdict: {res.verdict.label.value} "
          f"({res.verdict.confidence:.0%})", flush=True)
    reply = ab("message", "reply", inbox_id, message_id, "--text", res.card_markdown)
    print(f"[e2e] reply sent: {reply.get('id')}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
