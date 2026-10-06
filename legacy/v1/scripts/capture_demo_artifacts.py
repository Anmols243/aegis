"""Capture real pipeline artifacts for deterministic demo replay.

Runs ONE live analysis of the sample phish (production path) and saves the
full result as JSON under demo/artifacts/. `scripts/demo.py --mode
deterministic` replays these artifacts with zero LLM calls — a guaranteed
reproducible judge experience built from real outputs, not fakes.

Usage: python scripts/capture_demo_artifacts.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from aegis.agents.redteam import mutate_with_axes  # noqa: E402
from aegis.orchestrator import analyze_email  # noqa: E402
from smoke_llm import SAMPLE_PHISH_BODY  # noqa: E402

ART_DIR = os.path.join(os.path.dirname(__file__), "..", "demo", "artifacts")


def _ser(obj):
    """Recursive serializer for the pipeline's dataclasses."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_ser(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _ser(v) for k, v in obj.items()}
    if hasattr(obj, "__dataclass_fields__"):
        out = {}
        for f in obj.__dataclass_fields__:
            v = getattr(obj, f)
            if f == "screenshot_path":
                continue  # local temp path, not portable
            out[f] = _ser(v)
        # Enums -> values
        for k, v in list(out.items()):
            if hasattr(v, "value"):
                out[k] = v.value
        return out
    if hasattr(obj, "value"):  # Enum
        return obj.value
    return str(obj)


def main() -> int:
    os.makedirs(ART_DIR, exist_ok=True)

    print("[capture] running live pipeline on the sample phish ...")
    res = analyze_email("demo-artifact-phish-001", SAMPLE_PHISH_BODY,
                        agentboxd_scores={"phishing": 0.92})
    artifact = {
        "email_id": res.email_id,
        "raw_body": SAMPLE_PHISH_BODY,  # the analyzed source — every
        # captured quote is verifiable against this text
        "triage": _ser(res.triage.__dict__),
        "signals": _ser([s.__dict__ for s in res.signals.signals]),
        "forensic": _ser(res.forensic),
        "vision": _ser(res.vision),
        "sandbox": _ser(res.sandbox),
        "verdict": _ser(res.verdict.__dict__),
        "card_markdown": res.card_markdown,
        "campaign_note": res.campaign_note,
        "stage_timings": res.stage_timings,
        "note": "Captured from a real AEGIS pipeline run. "
                "Deterministic replay only — no live calls.",
    }
    path = os.path.join(ART_DIR, "scam-analysis.json")
    with open(path, "w") as f:
        json.dump(artifact, f, indent=2)
    print(f"[capture] wrote {path}")

    print("[capture] generating deterministic red-team mutation ...")
    variants = mutate_with_axes(SAMPLE_PHISH_BODY, n=5)
    mutations = [{"axes": v.axes, "text": v.text} for v in variants]
    mpath = os.path.join(ART_DIR, "redteam-mutations.json")
    with open(mpath, "w") as f:
        json.dump({"seed": 20261005, "variants": mutations}, f, indent=2)
    print(f"[capture] wrote {mpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
