"""AEGIS one-command narrative demo — the video shot list as runnable beats.

Beats:
  1 — live verdict: sample phish through the full pipeline, verdict card
  2 — threat graph: seed the parcel campaign, show a new inbound joining it
  3 — red team: mutate, attack, bank the misses (condensed report)
  4 — eval: synthetic 15-message corpus results (reads eval/results.json,
      runs the eval first if missing)

Usage: python scripts/demo.py [--beat 1|2|3|4] [--all]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from aegis.orchestrator import analyze_email  # noqa: E402
from aegis.graph.store import EmailEntities, ThreatGraph  # noqa: E402
from aegis.agents.redteam import mutate_with_axes, run_regression  # noqa: E402
from smoke_llm import SAMPLE_PHISH_BODY  # noqa: E402


def banner(title: str) -> None:
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)


def beat1() -> None:
    banner("BEAT 1 — a scam arrives, the agents dissect it")
    res = analyze_email("demo-phish-001", SAMPLE_PHISH_BODY)
    v = res.verdict
    print(f"verdict: {v.label.value}  confidence {v.confidence:.0%}  "
          f"score {v.score:.2f}")
    if res.forensic:
        print(f"forensic risk: {res.forensic.risk_score:.2f}")
        for f in res.forensic.findings[:4]:
            print(f"  - [{f.severity}] {f.claim}")
    if v.dissent:
        print("dissent:", "; ".join(v.dissent))
    print("\nverdict card preview:")
    print((res.card_markdown or "")[:600])


def beat2() -> None:
    banner("BEAT 2 — the threat graph links the campaign")
    import seed_campaign  # noqa: E402
    seed_campaign.main()
    g = ThreatGraph()
    g.add_email(EmailEntities(
        email_id="demo-inbound-parcel",
        senders=["ParcelTrack <notify@parcel-track-notify.com>"],
        domains=["parcel-track-notify.com"],
        urls=["http://parcel-track-notify.com/redelivery?pkg=12345"],
        phones=["+1-800-555-0142"],
        body="Package 12345 held. Pay $2.95 now: "
             "http://parcel-track-notify.com/redelivery?pkg=12345",
    ))
    camp = g.campaign_for("demo-inbound-parcel") or set()
    n = sum(1 for x in camp if x.startswith("email:"))
    print(f"\nnew inbound shares infrastructure with {n - 1} earlier scams "
          f"-> verdict card will cite the campaign")


def beat3() -> None:
    banner("BEAT 3 — the red team attacks")
    variants = mutate_with_axes(SAMPLE_PHISH_BODY, n=5)
    print(f"engine generated {len(variants)} adversarial variants "
          f"(seeded, reproducible)\n")
    report = run_regression(fresh_variants=variants)
    print(f"\nRED-TEAM REPORT: {report.caught}/{report.total} reached SCAM")
    for c in report.missed:
        print(f"  missed -> {c.id}: {c.actual_label} @ {c.score:.2f} "
              f"[{', '.join(c.mutation_axes)}] (banked)")


def beat4() -> None:
    banner("BEAT 4 — synthetic eval (honest small-n numbers)")
    rpath = os.path.join(os.path.dirname(__file__), "..", "eval", "results.json")
    if not os.path.exists(rpath):
        print("no eval/results.json — running eval now (takes ~20 min)...")
        import eval as eval_mod  # noqa: E402
        sys.argv = ["eval.py"]
        eval_mod.main()
    data = json.load(open(rpath))
    s = data["summary"]
    print(f"n={s['n']} ({s['note']})")
    print(f"  scam recall@flagged : {s['scam_recall_at_flagged']:.0%}")
    print(f"  scam recall@SCAM    : {s['scam_recall_at_SCAM']:.0%}")
    print(f"  legit specificity   : {s['legit_specificity']:.0%}")


BEATS = {"1": beat1, "2": beat2, "3": beat3, "4": beat4}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--beat", choices=list(BEATS))
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    beats = list(BEATS) if args.all or not args.beat else [args.beat]
    for b in beats:
        BEATS[b]()
    print("\n[demos] done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
