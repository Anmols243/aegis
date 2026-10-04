"""Red-team loop: mutate real scams, probe the pipeline, bank the misses.

CONTRACT (Phase 5):
  mutate(email_body: str, n: int = 5) -> list[str]      # adversarial variants
  run_regression(corpus_dir="tests/regression") -> RegressionReport

The mutator preserves malicious intent while changing the surface:
rephrased lure, fresh lookalike domain, different impersonated brand,
altered urgency framing, reordered structure.

Each variant runs through orchestrator.analyze_email(). Variants scoring
below the SCAM threshold are saved as JSON fixtures in tests/regression/
with the expected label — permanent regression tests, and the demo's climax.
"""
from __future__ import annotations

from dataclasses import dataclass, field

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
    variant: str
    expected_label: str = "SCAM"
    actual_label: str = ""
    score: float = 0.0

    @property
    def missed(self) -> bool:
        return self.actual_label != self.expected_label


@dataclass
class RegressionReport:
    total: int = 0
    caught: int = 0
    missed: list[RegressionCase] = field(default_factory=list)


def mutate(email_body: str, n: int = 5) -> list[str]:
    """Phase 5: MODEL_REDTEAM generates n adversarial variants."""
    raise NotImplementedError("Phase 5 — see BUILD_PLAN.md")


def run_regression(corpus_dir: str = "tests/regression") -> RegressionReport:
    """Phase 5: run stored + fresh variants through the pipeline; bank misses."""
    raise NotImplementedError("Phase 5 — see BUILD_PLAN.md")
