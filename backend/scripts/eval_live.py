"""Evaluate the running backend with real models.

Submits the eval corpus (../eval/corpus.json) plus the built-in samples to a
live API, waits for every verdict, and writes ../eval/RESULTS.md and
../eval/results_v2.json.

    python scripts/eval_live.py [--base http://127.0.0.1:8000] [--api-key KEY]

"Flagged" = SCAM or SUSPICIOUS. Small synthetic set: a sanity check of the
pipeline, not a real-world accuracy claim.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

import httpx

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

from aegis.services.samples import SAMPLES  # noqa: E402


def cases() -> list[dict]:
    with open(os.path.join(ROOT, "eval", "corpus.json"), encoding="utf-8") as f:
        corpus = json.load(f)
    out = [{"id": c["id"], "expected": "SCAM" if c["expected"] == "scam" else "LIKELY_SAFE",
            "body": {"raw": c["text"]}, "set": "corpus"} for c in corpus]
    out += [{"id": s["id"], "expected": s["expected"], "body": {"sample_id": s["id"]},
             "set": "samples"} for s in SAMPLES]
    return out


def submit(c: httpx.Client, body: dict) -> str:
    while True:
        r = c.post("/api/v1/analyses", json=body)
        if r.status_code == 429:
            time.sleep(int(r.headers.get("retry-after", "5")))
            continue
        r.raise_for_status()
        return r.json()["id"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--api-key", default=os.environ.get("AEGIS_API_KEY"))
    args = ap.parse_args()
    headers = {"Authorization": f"Bearer {args.api_key}"} if args.api_key else {}
    rows = []
    with httpx.Client(base_url=args.base, headers=headers, timeout=30) as c:
        todo = cases()
        for case in todo:
            case["analysis_id"] = submit(c, case["body"])
            print(f"submitted {case['id']}", flush=True)
        for case in todo:
            while True:
                a = c.get(f"/api/v1/analyses/{case['analysis_id']}").json()
                if a["status"] in ("done", "failed"):
                    break
                time.sleep(2)
            failed = [s["name"] for s in a["stages"] if s["status"] == "failed"]
            rows.append({"id": case["id"], "set": case["set"], "expected": case["expected"],
                         "label": a.get("label"), "score": a.get("score"),
                         "duration_s": a.get("duration_s"), "failed_stages": failed,
                         "corroboration": (a.get("verdict") or {}).get("corroboration", [])})
            print(f"{case['id']:<24} expected {case['expected']:<11} got {a.get('label')}",
                  flush=True)

    scams = [r for r in rows if r["expected"] == "SCAM"]
    legit = [r for r in rows if r["expected"] == "LIKELY_SAFE"]
    flagged = lambda r: r["label"] in ("SCAM", "SUSPICIOUS")  # noqa: E731
    tp = sum(flagged(r) for r in scams)
    fp = sum(flagged(r) for r in legit)
    recall_flag = tp / len(scams)
    recall_scam = sum(r["label"] == "SCAM" for r in scams) / len(scams)
    spec = sum(r["label"] == "LIKELY_SAFE" for r in legit) / len(legit)
    precision = tp / (tp + fp) if tp + fp else 0.0
    durs = sorted(r["duration_s"] for r in rows if r["duration_s"])
    summary = {
        "n": len(rows), "scams": len(scams), "legit": len(legit),
        "scam_recall_flagged": round(recall_flag, 3), "scam_recall_at_SCAM": round(recall_scam, 3),
        "legit_cleared": round(spec, 3), "precision_flagged": round(precision, 3),
        "latency_mean_s": round(statistics.mean(durs), 1) if durs else None,
        "latency_p50_s": durs[len(durs) // 2] if durs else None,
        "latency_max_s": durs[-1] if durs else None,
        "runs_with_failed_stage": sum(bool(r["failed_stages"]) for r in rows),
    }
    with open(os.path.join(ROOT, "eval", "results_v2.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": rows}, f, indent=2)
    lines = ["# AEGIS v2 evaluation (real models, live API)", "",
             f"Run: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}. "
             "Synthetic set: a pipeline sanity check, not a real-world accuracy claim.", "",
             "| Metric | Value |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in summary.items()]
    lines += ["", "| Case | Set | Expected | Verdict | Score | Time (s) |", "|---|---|---|---|---|---|"]
    lines += [f"| {r['id']} | {r['set']} | {r['expected']} | {r['label']} | {r['score']} | "
              f"{r['duration_s']} |" for r in rows]
    with open(os.path.join(ROOT, "eval", "RESULTS.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
