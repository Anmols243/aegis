"""False-positive check: run clearly-legitimate emails through the live pipeline.

Prints verdict + score per sample. Expect LIKELY_SAFE; anything SCAM is a
calibration bug worth investigating before the demo.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aegis.orchestrator import analyze_email

SAMPLES = {
    "legit-order-confirm": (
        "From: orders@example-store.com\n"
        "Subject: Your order #48291 has shipped\n\n"
        "Hi Anmol,\n\n"
        "Good news — your order #48291 shipped today via Standard Post.\n"
        "Track it here: https://example-store.com/track/48291\n\n"
        "Estimated delivery: Oct 9. Reply to this email if anything looks wrong.\n\n"
        "Thanks,\nThe Example Store team"
    ),
    "legit-newsletter": (
        "From: newsletter@pyweekly.example\n"
        "Subject: PyWeekly #812\n\n"
        "This week's highlights:\n"
        "- A deep dive into pattern matching performance\n"
        "- Three new releases in the data-viz space\n\n"
        "Read online: https://pyweekly.example/issues/812\n"
        "Unsubscribe: https://pyweekly.example/unsub/abc123"
    ),
    "legit-bank-alert": (
        "From: alerts@mybank.example\n"
        "Subject: New device signed in\n\n"
        "Hi,\n\n"
        "A new device signed in to your account on Oct 4 from Mumbai, IN.\n"
        "If this was you, no action is needed.\n"
        "If you don't recognize it, secure your account: https://mybank.example/security\n\n"
        "— MyBank security team"
    ),
}


def main() -> None:
    for case_id, raw in SAMPLES.items():
        res = analyze_email(case_id, raw)
        v = res.verdict
        print(f"{case_id}: {v.label.value} (score={v.score:.2f}, conf={v.confidence:.2f})")
        if v.dissent:
            print(f"  dissent: {v.dissent}")


if __name__ == "__main__":
    main()
