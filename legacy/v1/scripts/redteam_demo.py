"""Red-team demo run: mutate the sample phish, attack the live pipeline, bank misses.

Usage:  python scripts/redteam_demo.py [--variants N]

1. Deterministic red-team engine generates N adversarial variants of the
   sample PayPal phish — homoglyph brands, fresh lookalike domains, TLD
   swaps, brand-as-subdomain, rephrased urgency/lures, restructured layout.
   (Seeded: same input -> same variants, every run. An LLM mutator was tried
   first and refused to emit deployable phish — correct call, and exactly
   why the demo can't depend on one.)
2. Each variant is replayed through the live pipeline (triage -> forensic ->
   sandbox -> arbiter; LLM stages via the vault-backed Featherless skill).
3. Misses are saved as regression fixtures in tests/regression/ — the
   pipeline's immune system. Run again later and `caught_after_fix` flips.

Prints a judges-friendly report. No keys in env/files.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from smoke_llm import SAMPLE_PHISH_BODY  # noqa: E402

from aegis.agents.redteam import mutate_with_axes, run_regression  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", type=int, default=5)
    args = ap.parse_args()

    print(f"[redteam] mutating sample phish into {args.variants} variants...")
    variants = mutate_with_axes(SAMPLE_PHISH_BODY, n=args.variants)
    print(f"[redteam] got {len(variants)} variants, attacking pipeline...\n")

    for i, v in enumerate(variants, 1):
        print(f"--- variant {i} [{', '.join(v.axes)}] ---")
        print(v.text[:300].replace("\n", " ") + ("..." if len(v.text) > 300 else ""))
        print()

    report = run_regression(fresh_variants=variants)

    print("=" * 60)
    print(f"RED-TEAM REPORT: {report.caught}/{report.total} variants caught")
    if report.missed:
        print(f"{len(report.missed)} MISSED — banked as regression fixtures:")
        for c in report.missed:
            print(f"  - {c.id}: verdict={c.actual_label} score={c.score:.2f}")
            print(f"    axes: {', '.join(c.mutation_axes)}")
            print(f"    preview: {c.variant[:120].replace(chr(10), ' ')}...")
    else:
        print("Zero misses — the pipeline held against every mutation.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
