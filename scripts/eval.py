"""Synthetic evaluation: run eval/corpus.json through the live pipeline.

Reports honest, small-n metrics — this is a synthetic set, not a claim about
real-world accuracy. Metrics:
  - scam recall@flagged: fraction of scam messages labeled SCAM or SUSPICIOUS
  - scam recall@SCAM: fraction labeled SCAM
  - legit specificity: fraction of legit messages labeled LIKELY_SAFE

Writes eval/results.json (per-message verdicts + summary).
Usage: python scripts/eval.py [--corpus eval/corpus.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from aegis.orchestrator import analyze_email  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=os.path.join(
        os.path.dirname(__file__), "..", "eval", "corpus.json"))
    args = ap.parse_args()

    with open(args.corpus) as f:
        corpus = json.load(f)

    rows = []
    for i, item in enumerate(corpus, 1):
        t0 = time.time()
        res = analyze_email(item["id"], item["text"])
        dt = time.time() - t0
        label = res.verdict.label.value
        rows.append({"id": item["id"], "expected": item["expected"],
                     "predicted": label, "score": round(res.verdict.score, 3),
                     "seconds": round(dt, 1)})
        print(f"[{i}/{len(corpus)}] {item['id']}: exp={item['expected']} "
              f"pred={label} score={res.verdict.score:.2f} ({dt:.0f}s)")

    scams = [r for r in rows if r["expected"] == "scam"]
    legits = [r for r in rows if r["expected"] == "legit"]
    summary = {
        "n": len(rows),
        "scam_recall_at_flagged": sum(r["predicted"] in ("SCAM", "SUSPICIOUS")
                                     for r in scams) / len(scams),
        "scam_recall_at_SCAM": sum(r["predicted"] == "SCAM"
                                  for r in scams) / len(scams),
        "legit_specificity": sum(r["predicted"] == "LIKELY_SAFE"
                                for r in legits) / len(legits),
        "note": "synthetic 15-message set (7 scam incl. 6 adversarial variants, "
                "8 legit). Not a real-world accuracy claim.",
    }
    out = {"rows": rows, "summary": summary}
    rpath = os.path.join(os.path.dirname(args.corpus), "results.json")
    with open(rpath, "w") as f:
        json.dump(out, f, indent=2)

    print("\n--- EVAL SUMMARY (synthetic, n=15) ---")
    print(f"scam recall@flagged : {summary['scam_recall_at_flagged']:.0%}")
    print(f"scam recall@SCAM    : {summary['scam_recall_at_SCAM']:.0%}")
    print(f"legit specificity   : {summary['legit_specificity']:.0%}")
    print(f"results -> {rpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
