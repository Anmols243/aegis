"""AEGIS one-command narrative demo — the video shot list as runnable beats.

MODES:
  live          — real pipeline, real LLM calls (default)
  deterministic — replays captured real artifacts from demo/artifacts/
                  (zero LLM calls, guaranteed reproducible)

Beats:
  1 — live verdict: sample phish through the full pipeline, verdict card
  2 — threat graph: seed the parcel campaign, show a new inbound joining it
  3 — red team: mutate, attack, bank the misses (condensed report)
  4 — eval: synthetic 15-message corpus results (reads eval/results.json,
      runs the eval first if missing)

Usage:
  python scripts/demo.py [--beat 1|2|3|4] [--all] [--mode live|deterministic]
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


def _print_beat1(res, tag: str) -> None:
    v = res.verdict
    print(f"[{tag}] verdict: {v.label.value}  confidence {v.confidence:.0%}  "
          f"score {v.score:.2f}")
    if res.forensic:
        print(f"forensic risk: {res.forensic.risk_score:.2f}")
        for f in res.forensic.findings[:4]:
            print(f"  - [{f.severity}] {f.claim}")
    if v.dissent:
        print("dissent:", "; ".join(v.dissent))


def beat1() -> None:
    banner("BEAT 1 — a scam arrives, the agents dissect it")
    res = analyze_email("demo-phish-001", SAMPLE_PHISH_BODY)
    _print_beat1(res, "standalone")
    print("\n--- with the AgentBoxD phishing signal (production path) ---")
    res2 = analyze_email("demo-phish-001-prod", SAMPLE_PHISH_BODY,
                         agentboxd_scores={"phishing": 0.92})
    _print_beat1(res2, "production")
    print("\nverdict card preview:")
    print((res2.card_markdown or "")[:600])


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
    if "scam_f1" in s:
        print(f"  precision/recall/F1 : {s['scam_precision']:.0%} / "
              f"{s['scam_recall']:.0%} / {s['scam_f1']:.0%}")
    if "latency_s" in s:
        l = s["latency_s"]
        print(f"  latency mean/p50/p95: {l['mean']}s / {l['p50']}s / {l['p95']}s")


ART_DIR = os.path.join(os.path.dirname(__file__), "..", "demo", "artifacts")


def _load_artifact(name: str) -> dict:
    path = os.path.join(ART_DIR, name)
    if not os.path.exists(path):
        print(f"[demo] missing artifact {path} — run "
              f"scripts/capture_demo_artifacts.py first")
        sys.exit(2)
    return json.load(open(path))


def beat1_deterministic() -> None:
    """Replay the captured scam analysis, stage by stage. No LLM calls."""
    banner("BEAT 1 (deterministic replay) — a scam arrives, dissected")
    a = _load_artifact("scam-analysis.json")
    print(f"\n[1. triage] sender: {a['triage'].get('sender')}")
    print(f"    urls: {a['triage'].get('urls')}")
    print(f"    brands: {a['triage'].get('brand_mentions')}")
    print("\n[2. deterministic signals] verified facts, zero LLM:")
    if a["signals"]:
        for s in a["signals"][:6]:
            print(f"    [{s['severity']}] {s['name']}: {s['detail']}")
    else:
        print("    (none fired — this sample carries no headers; signals fire "
              "on From/Reply-To/auth/URL mismatches in real mail)")
    print("\n[3. forensic] evidence-cited findings:")
    for f in a["forensic"]["findings"][:4]:
        print(f"    - [{f['severity']}] {f['claim']}")
        print(f"      evidence: \"{f['evidence']['excerpt'][:80]}\"")
    print(f"    risk_score: {a['forensic']['risk_score']}")
    print("\n[4. sandbox] URL investigation:")
    for s in a["sandbox"]:
        print(f"    {s['url'][:60]} -> {s['kind']} "
              f"(status={s.get('status_code')}, "
              f"{s.get('fetch_duration_s')}s)")
    print(f"\n[5. campaign] {a['campaign_note'] or '(no campaign linkage)'}")
    v = a["verdict"]
    print(f"\n[6. arbiter] verdict: {v['label']}  score {v['score']:.2f}  "
          f"confidence {v['confidence']:.0%}")
    print(f"    agreement: {v.get('agreement')} · strongest: "
          f"{', '.join(v.get('strongest', []))}")
    if v.get("dissent"):
        print(f"    dissent: {'; '.join(v['dissent'])}")
    print("\n[7. verdict card]")
    print(a["card_markdown"][:800])


def beat3_deterministic() -> None:
    """Replay the captured red-team mutations. No LLM calls."""
    banner("BEAT 3 (deterministic replay) — the red team attacks")
    m = _load_artifact("redteam-mutations.json")
    print(f"engine generated {len(m['variants'])} adversarial variants "
          f"(seed {m['seed']}, reproducible)\n")
    for i, var in enumerate(m["variants"], 1):
        print(f"  variant {i}: [{', '.join(var['axes'])}]")
    print("\nEach miss becomes a permanent regression fixture in "
          "tests/regression/ — the pipeline's immune system.")


BEATS = {"1": beat1, "2": beat2, "3": beat3, "4": beat4}
BEATS_DET = {"1": beat1_deterministic, "3": beat3_deterministic}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--beat", choices=list(BEATS))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--mode", choices=["live", "deterministic"],
                    default="live")
    args = ap.parse_args()
    beats = list(BEATS) if args.all or not args.beat else [args.beat]
    table = BEATS_DET if args.mode == "deterministic" else BEATS
    for b in beats:
        fn = table.get(b, BEATS[b])  # beats 2/4 have no replay variant
        if args.mode == "deterministic" and b not in BEATS_DET:
            print(f"\n[demo] beat {b} has no deterministic variant — "
                  f"running live")
        fn()
    print("\n[demos] done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
