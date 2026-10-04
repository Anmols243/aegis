"""Synthetic evaluation: run eval/corpus.json through the live pipeline.

Reports honest, small-n metrics — this is a synthetic set, not a claim about
real-world accuracy. Metrics:
  - confusion matrix (expected x predicted)
  - scam precision / recall / F1 (positive = flagged = SCAM|SUSPICIOUS)
  - scam recall@flagged, recall@SCAM, legit specificity
  - latency: mean / p50 / p95 overall + per-stage

Ablation flags let you measure component value without extra LLM cost for
the deterministic parts:
  --no-signals   skip the deterministic signal layer
  --no-sandbox   skip URL sandboxing
  --no-vision    skip the vision inspector (needs --html corpus anyway)

Writes eval/results.json (per-message verdicts + summary + metrics).
Usage: python scripts/eval.py [--corpus eval/corpus.json] [--no-signals]
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from aegis import orchestrator as orch  # noqa: E402
from aegis.orchestrator import analyze_email  # noqa: E402

LABELS = ("SCAM", "SUSPICIOUS", "LIKELY_SAFE")


def _pct(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    k = (len(s) - 1) * q
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=os.path.join(
        os.path.dirname(__file__), "..", "eval", "corpus.json"))
    ap.add_argument("--no-signals", action="store_true",
                    help="ablate the deterministic signal layer")
    ap.add_argument("--no-sandbox", action="store_true",
                    help="ablate the URL sandbox")
    ap.add_argument("--no-vision", action="store_true",
                    help="ablate the vision inspector")
    ap.add_argument("--out", default=None,
                    help="results path (default: next to corpus)")
    args = ap.parse_args()

    # Ablation: patch the orchestrator's stage bindings, not the modules.
    patches = []
    if args.no_signals:
        from aegis.agents import signals as sig_mod

        def _empty(*a, **k):
            return sig_mod.SignalReport(signals=[])
        patches.append(__import__("unittest.mock", fromlist=["patch"]).patch.object(
            orch, "analyze_signals", _empty))
    if args.no_sandbox:
        def _nosb(urls):
            return []
        patches.append(__import__("unittest.mock", fromlist=["patch"]).patch(
            "aegis.agents.sandbox.inspect_urls", _nosb))
    if args.no_vision:
        patches.append(__import__("unittest.mock", fromlist=["patch"]).patch(
            "aegis.agents.vision_inspector.inspect",
            side_effect=RuntimeError("ablated")))
    for p in patches:
        p.start()

    try:
        with open(args.corpus) as f:
            corpus = json.load(f)

        rows = []
        stage_times: dict[str, list[float]] = {}
        for i, item in enumerate(corpus, 1):
            t0 = time.time()
            res = analyze_email(item["id"], item["text"],
                                html=item.get("html", ""))
            dt = time.time() - t0
            for stage, t in (res.stage_timings or {}).items():
                stage_times.setdefault(stage, []).append(t.get("seconds", 0))
            label = res.verdict.label.value
            rows.append({
                "id": item["id"], "expected": item["expected"],
                "predicted": label, "score": round(res.verdict.score, 3),
                "confidence": res.verdict.confidence,
                "agreement": res.verdict.agreement,
                "seconds": round(dt, 1),
                "stage_seconds": {k: v.get("seconds") for k, v in
                                  (res.stage_timings or {}).items()},
            })
            print(f"[{i}/{len(corpus)}] {item['id']}: exp={item['expected']} "
                  f"pred={label} score={res.verdict.score:.2f} ({dt:.0f}s)")
    finally:
        for p in patches:
            p.stop()

    scams = [r for r in rows if r["expected"] == "scam"]
    legits = [r for r in rows if r["expected"] == "legit"]
    flagged = lambda r: r["predicted"] in ("SCAM", "SUSPICIOUS")  # noqa: E731

    tp = sum(flagged(r) for r in scams)
    fp = sum(flagged(r) for r in legits)
    fn = len(scams) - tp
    tn = len(legits) - fp
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    lat = [r["seconds"] for r in rows]
    summary = {
        "n": len(rows),
        "ablation": {
            "no_signals": args.no_signals,
            "no_sandbox": args.no_sandbox,
            "no_vision": args.no_vision,
        },
        # legacy fields (demo.py beat 4 reads these)
        "scam_recall_at_flagged": recall,
        "scam_recall_at_SCAM": sum(r["predicted"] == "SCAM"
                                   for r in scams) / len(scams),
        "legit_specificity": tn / len(legits) if legits else 0.0,
        # confusion matrix: expected -> predicted counts
        "confusion": {
            exp: {pred: sum(1 for r in rows if r["expected"] == exp
                            and r["predicted"] == pred)
                  for pred in LABELS}
            for exp in ("scam", "legit")
        },
        "scam_precision": round(precision, 3),
        "scam_recall": round(recall, 3),
        "scam_f1": round(f1, 3),
        "false_positive_rate": round(fp / len(legits), 3) if legits else 0.0,
        "false_negative_rate": round(fn / len(scams), 3) if scams else 0.0,
        "latency_s": {
            "mean": round(statistics.mean(lat), 1),
            "p50": round(_pct(lat, 0.5), 1),
            "p95": round(_pct(lat, 0.95), 1),
        },
        "stage_latency_s": {
            stage: {"mean": round(statistics.mean(ts), 2),
                    "p95": round(_pct(ts, 0.95), 2)}
            for stage, ts in stage_times.items()
        },
        "note": "synthetic 15-message set (7 scam incl. 6 adversarial "
                "variants, 8 legit). Not a real-world accuracy claim.",
    }
    out = {"rows": rows, "summary": summary}
    rpath = args.out or os.path.join(os.path.dirname(args.corpus),
                                     "results.json")
    with open(rpath, "w") as f:
        json.dump(out, f, indent=2)

    print("\n--- EVAL SUMMARY (synthetic, n=%d) ---" % len(rows))
    print(f"precision / recall / F1 (flagged): "
          f"{precision:.0%} / {recall:.0%} / {f1:.0%}")
    print(f"scam recall@SCAM    : {summary['scam_recall_at_SCAM']:.0%}")
    print(f"legit specificity   : {summary['legit_specificity']:.0%}")
    print(f"latency mean/p50/p95: {summary['latency_s']['mean']}s / "
          f"{summary['latency_s']['p50']}s / {summary['latency_s']['p95']}s")
    for stage, s in summary["stage_latency_s"].items():
        print(f"  {stage:10s} mean {s['mean']}s p95 {s['p95']}s")
    print(f"results -> {rpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
