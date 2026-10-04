"""Build eval/corpus.json: 8 scam + 8 legit messages, deterministic.

Scam set: the sample PayPal phish + 7 adversarial variants from the
deterministic red-team engine (two seeds). Legit set: hand-written everyday
mail. Re-run to regenerate identically.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from smoke_llm import SAMPLE_PHISH_BODY  # noqa: E402
from aegis.agents.redteam import mutate_with_axes  # noqa: E402

LEGIT = {
    "legit-order": (
        "From: orders@example-store.com\nSubject: Your order #48291 has shipped\n\n"
        "Hi Anmol,\n\nGood news — your order #48291 shipped today via Standard Post.\n"
        "Track it here: https://example-store.com/track/48291\n\n"
        "Estimated delivery: Oct 9. Reply to this email if anything looks wrong.\n\n"
        "Thanks,\nThe Example Store team"
    ),
    "legit-newsletter": (
        "From: newsletter@pyweekly.example\nSubject: PyWeekly #812\n\n"
        "This week's highlights:\n"
        "- A deep dive into pattern matching performance\n"
        "- Three new releases in the data-viz space\n\n"
        "Read online: https://pyweekly.example/issues/812\n"
        "Unsubscribe: https://pyweekly.example/unsub/abc123"
    ),
    "legit-bank-alert": (
        "From: alerts@mybank.example\nSubject: New device signed in\n\n"
        "Hi,\n\nA new device signed in to your account on Oct 4 from Mumbai, IN.\n"
        "If this was you, no action is needed.\n"
        "If you don't recognize it, secure your account: https://mybank.example/security\n\n"
        "— MyBank security team"
    ),
    "legit-meeting": (
        "From: priya@example-corp.com\nSubject: Design review moved to Thursday\n\n"
        "Hi all,\n\nMoving our design review to Thursday 3pm IST — same Meet link as usual.\n"
        "Agenda: onboarding flow mockups (v3), empty states.\n"
        "Let me know if the time doesn't work.\n\nPriya"
    ),
    "legit-flight": (
        "From: bookings@example-air.com\nSubject: Your itinerary: BOM → DEL, Oct 18\n\n"
        "Hi Anmol,\n\nYour booking is confirmed:\n"
        "AI-654 · BOM → DEL · Oct 18, 07:10 → 09:25 · Seat 14A\n\n"
        "Manage booking: https://example-air.com/manage/XT7K2P\n"
        "Check-in opens 48 hours before departure.\n\nSafe travels!"
    ),
    "legit-interview": (
        "From: hiring@example-startup.com\nSubject: Interview invitation — backend intern\n\n"
        "Hi Anmol,\n\nThanks for applying! We'd like to invite you to a 45-minute technical "
        "interview next week. Available slots:\n"
        "- Tue Oct 7, 11:00 IST\n- Wed Oct 8, 16:00 IST\n\n"
        "Reply with what works. Looking forward to it!\n\n— Riya, Engineering"
    ),
    "legit-bill": (
        "From: billing@example-power.com\nSubject: Your September electricity bill\n\n"
        "Hi,\n\nYour September bill of Rs 1,842 is due Oct 15.\n"
        "View or pay: https://example-power.com/pay/acct-77821\n\n"
        "This is an automated message — please don't reply."
    ),
    "legit-personal": (
        "From: kabir@example-mail.com\nSubject: dinner saturday?\n\n"
        "hey — a few of us are doing dinner at that new place in bandra on saturday, "
        "around 8. you in? let me know by friday so i can book.\n\n- k"
    ),
}


def main() -> None:
    corpus = []
    corpus.append({"id": "scam-paypal-orig", "expected": "scam",
                   "text": SAMPLE_PHISH_BODY})
    n = 1
    for seed in (20261005, 777):
        for m in mutate_with_axes(SAMPLE_PHISH_BODY, n=4, seed=seed):
            # skip duplicates across seeds
            if any(c["text"] == m.text for c in corpus):
                continue
            n += 1
            corpus.append({"id": f"scam-paypal-var{n:02d}", "expected": "scam",
                           "text": m.text, "axes": m.axes})
            if n == 7:
                break
        if n == 7:
            break
    for cid, text in LEGIT.items():
        corpus.append({"id": cid, "expected": "legit", "text": text})
    out = os.path.join(os.path.dirname(__file__), "..", "eval", "corpus.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(corpus, f, indent=2)
    scams = sum(1 for c in corpus if c["expected"] == "scam")
    legits = sum(1 for c in corpus if c["expected"] == "legit")
    print(f"wrote {out}: {scams} scam + {legits} legit = {len(corpus)}")


if __name__ == "__main__":
    main()
