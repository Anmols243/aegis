"""AEGIS poller — demo-friendly alternative to webhooks.

Long-polls the AgentBoxD inbox for new mail, runs the full pipeline, and
replies with the verdict card in-thread. No public URL needed.

Usage:
    AEGIS_INBOX_ID=<id> python scripts/poller.py
Runs until Ctrl-C.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import httpx

from aegis import notify
from aegis.orchestrator import analyze_email

BASE = "https://api.agentboxd.com"


def main() -> None:
    inbox_id = os.environ["AEGIS_INBOX_ID"]
    api_key = os.environ["AGENTBOXD_API_KEY"]
    print(f"[poller] watching inbox {inbox_id}", flush=True)
    print("[poller] forward a suspicious email to the inbox address — "
          "the verdict reply lands in-thread.", flush=True)
    since: str | None = None
    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(base_url=BASE, headers=headers, timeout=70.0) as c:
        while True:
            params: dict = {"timeout": 60, "direction": "inbound"}
            if since:
                params["since"] = since
            try:
                r = c.get(f"/v1/inboxes/{inbox_id}/messages/wait", params=params)
                r.raise_for_status()
                stub = r.json().get("data")
            except Exception as e:  # noqa: BLE001 — poller must survive blips
                print(f"[poller] wait error: {e}", flush=True)
                time.sleep(5)
                continue
            if not stub:
                continue
            mid = stub.get("id")
            try:
                full = notify.get_message(mid)
            except Exception as e:
                print(f"[poller] fetch error on {mid}: {e}", flush=True)
                continue
            body = full.get("text") or full.get("extracted_text") or ""
            if not body and not full.get("html"):
                since = full.get("received_at") or full.get("created_at") or since
                continue
            print(f"[poller] analyzing {mid} ...", flush=True)
            try:
                res = analyze_email(
                    mid, body, full.get("headers") or "",
                    full.get("html") or "",
                    notify.message_scores(full),
                )
                notify.reply_to_message(inbox_id, mid, res.card_markdown)
                print(f"[poller] replied: {res.verdict.label.value} "
                      f"({res.verdict.confidence:.0%})", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"[poller] pipeline error on {mid}: {e}", flush=True)
            since = full.get("received_at") or full.get("created_at") or since


if __name__ == "__main__":
    main()
