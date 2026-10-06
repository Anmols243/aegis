"""Fill the live dashboard with sample verdicts — no inbox, no email sent.

1. Replays the captured real pipeline run (demo/artifacts/scam-analysis.json:
   full LLM forensic findings) as one dashboard entry.
2. Runs every email in eval/corpus.json through the actual pipeline and
   records each result. Without an LLM backend the AI stages degrade and
   verdicts are conservative (fail-closed); with FEATHERLESS_API_KEY set
   they run in full.

Entries are prefixed "sample-" so they're distinguishable from real mail.

Usage:
    PYTHONPATH=src python scripts/seed_dashboard.py
"""
import json
import os
import sys
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from aegis.dashboard.store import record  # noqa: E402
from aegis.orchestrator import analyze_email  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


def replay_artifact() -> None:
    with open(os.path.join(ROOT, "demo/artifacts/scam-analysis.json"),
              encoding="utf-8") as f:
        a = json.load(f)
    v = a["verdict"]
    res = NS(
        email_id="sample-captured-paypal-phish",
        verdict=NS(label=NS(value=v["label"]), confidence=v["confidence"],
                   score=v["score"], contributions=v["contributions"],
                   dissent=v["dissent"]),
        triage=NS(sender=a["triage"].get("sender") or ""),
        forensic=NS(risk_score=a["forensic"]["risk_score"], findings=[
            NS(claim=f["claim"], severity=f["severity"],
               evidence=NS(excerpt=f["evidence"]["excerpt"]))
            for f in a["forensic"]["findings"]]),
        sandbox=[NS(risk=s.get("risk", 0.3)) for s in a["sandbox"]],
        vision=None,
        signals=NS(signals=[NS(**s) for s in a["signals"]]),
        campaign_note=a["campaign_note"],
        stage_timings=a["stage_timings"],
    )
    record(res, a["raw_body"])
    print(f"[seed] replayed captured run -> {v['label']} ({v['score']:.2f})")


def run_corpus() -> None:
    with open(os.path.join(ROOT, "eval/corpus.json"), encoding="utf-8") as f:
        corpus = json.load(f)
    for item in corpus:
        res = analyze_email(f"sample-{item['id']}", item["text"])
        record(res, item["text"])
        print(f"[seed] {item['id']:<22} expected {item['expected']:<5} -> "
              f"{res.verdict.label.value} ({res.verdict.score:.2f})")


if __name__ == "__main__":
    replay_artifact()
    run_corpus()
