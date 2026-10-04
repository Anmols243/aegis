"""Red-team loop: mutate real scams, probe the pipeline, bank the misses.

- mutate(): MODEL_REDTEAM generates adversarial variants preserving intent.
- save_case() / run_regression(): misses become permanent JSON fixtures in
  tests/regression/ — the pipeline's immune system.
"""
from __future__ import annotations

import glob
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from ..config import get_settings
from ..llm import chat_json

REDTEAM_SYSTEM = """You are AEGIS-RedTeam, an adversarial tester for a scam detector.
Given a phishing email, generate MUTATED variants that preserve the malicious
intent but change the surface to evade detection.

Mutation axes (use 2-3 per variant):
- rephrase the lure in different words / tone
- swap the lookalike domain for a fresh one (homoglyphs, added words, new TLD)
- impersonate a different plausible brand
- change the urgency framing (deadline → account review → security alert)
- reorder / restructure the message

Return ONLY valid JSON: {"variants": ["full email text...", ...]}

Rules:
- Every variant must still be a scam a human could fall for — no gibberish.
- Do NOT include any verdict, analysis, or commentary — raw email text only.
- These are used to test a defensive system in a sandboxed hackathon demo."""


@dataclass
class RegressionCase:
    id: str
    variant: str
    expected_label: str = "SCAM"
    actual_label: str = ""
    score: float = 0.0
    first_missed_at: str = ""
    mutation_axes: list[str] = field(default_factory=list)
    caught_after_fix: bool = False

    @property
    def missed(self) -> bool:
        return self.actual_label != self.expected_label


@dataclass
class RegressionReport:
    total: int = 0
    caught: int = 0
    missed: list[RegressionCase] = field(default_factory=list)


def mutate(email_body: str, n: int = 5) -> list[str]:
    """Generate n adversarial variants of a phishing email."""
    model = get_settings().model_redteam
    data = chat_json(
        model,
        [
            {"role": "system", "content": REDTEAM_SYSTEM},
            {"role": "user",
             "content": f"Generate {n} mutated variants of this phishing email:\n\n{email_body}"},
        ],
        temperature=0.8,
    )
    variants = data.get("variants", [])
    return [v for v in variants if isinstance(v, str) and v.strip()][:n]


def save_case(case: RegressionCase, corpus_dir: str = "tests/regression") -> str:
    os.makedirs(corpus_dir, exist_ok=True)
    path = os.path.join(corpus_dir, f"{case.id}.json")
    with open(path, "w") as f:
        json.dump(asdict(case), f, indent=2)
    return path


def load_cases(corpus_dir: str = "tests/regression") -> list[RegressionCase]:
    cases = []
    for path in sorted(glob.glob(os.path.join(corpus_dir, "rt-*.json"))):
        with open(path) as f:
            d = json.load(f)
        known = set(RegressionCase.__dataclass_fields__)
        cases.append(RegressionCase(**{k: v for k, v in d.items() if k in known}))
    return cases


def _new_case_id(corpus_dir: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    existing = glob.glob(os.path.join(corpus_dir, f"rt-{ts}-*.json"))
    return f"rt-{ts}-{len(existing) + 1:03d}"


def run_regression(corpus_dir: str = "tests/regression",
                   fresh_variants: list[str] | None = None) -> RegressionReport:
    """Replay the corpus (+ any fresh variants) through the live pipeline.

    Needs FEATHERLESS_API_KEY etc. Misses are saved as new fixtures.
    """
    from ..orchestrator import analyze_email

    report = RegressionReport()
    cases = load_cases(corpus_dir)

    for i, variant in enumerate(fresh_variants or []):
        case_id = _new_case_id(corpus_dir)
        res = analyze_email(case_id, variant)
        case = RegressionCase(
            id=case_id, variant=variant, expected_label="SCAM",
            actual_label=res.verdict.label.value, score=res.verdict.score,
            first_missed_at=datetime.now(timezone.utc).isoformat(),
        )
        if case.missed:
            save_case(case, corpus_dir)
        cases.append(case)

    for case in cases:
        report.total += 1
        res = analyze_email(case.id, case.variant)
        case.actual_label = res.verdict.label.value
        case.score = res.verdict.score
        if case.missed:
            report.missed.append(case)
        else:
            report.caught += 1
            if not case.caught_after_fix:
                case.caught_after_fix = True
                save_case(case, corpus_dir)
    return report
