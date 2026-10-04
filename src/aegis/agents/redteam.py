"""Red-team loop: mutate real scams, probe the pipeline, bank the misses.

Deterministic adversarial engine — no LLM generation. We tried an LLM
mutator first (Kimi-K3); it refused to emit ready-to-send phishing text,
which is the correct safety call and also exactly why a judged live demo
can't depend on one: the engine must work every run. These mutations are
reproducible (seeded), versioned, and every miss becomes a permanent
regression fixture in tests/regression/ — the pipeline's immune system.
"""
from __future__ import annotations

import glob
import itertools
import json
import os
import random
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


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


def mutate(email_body: str, n: int = 5, seed: int = 20261005) -> list[str]:
    """Generate n adversarial variants of a phishing email (deterministic).

    Applies 2-3 mutation axes per variant from the engine below. Seeded, so
    the same input always yields the same variants — reproducible demos,
    reproducible regressions.
    """
    return [m.text for m in mutate_with_axes(email_body, n=n, seed=seed)]


@dataclass
class Mutation:
    text: str
    axes: list[str]


_URL_RE = re.compile(r"https?://[^\s)\"']+")

_FRESH_HOSTS = [
    "paypal-secure-verify.net",
    "pay-pal-security.com",
    "secure-paypal-verify.org",
    "paypalaccount-secure.net",
]

_URGENCY_SWAPS = [
    ("within 24 hours", "by end of business today"),
    ("immediately", "right away"),
    ("permanent suspension", "permanent closure of the account"),
    ("Failure to act will result in", "If you don't act now, this leads to"),
    ("unusual activity", "a suspicious sign-in attempt"),
]

_LURE_SWAPS = [
    ("verify your identity", "confirm your account ownership"),
    ("Dear Customer,", "Hello valued member,"),
    ("will be\nlimited", "will be\nrestricted"),
    ("will be limited", "will be restricted"),
]


def _m_homoglyph_brand(text: str) -> tuple[str, str] | None:
    """Cyrillic lookalikes in the brand name — attacks naive brand matching."""
    if "PayPal" not in text:
        return None
    return text.replace("PayPal", "P\u0430yP\u0430l"), "homoglyph-brand"


def _replace_url_host(text: str, new_host: str) -> str | None:
    m = _URL_RE.search(text)
    if not m:
        return None
    url = m.group(0)
    host = url.split("://", 1)[1].split("/", 1)[0]
    if host == new_host:
        return None
    return text.replace(url, url.replace(host, new_host, 1), 1)


def _m_fresh_domain(text: str) -> tuple[str, str] | None:
    """Swap the lookalike domain for a fresh one — evades domain blocklists."""
    m = _URL_RE.search(text)
    if not m:
        return None
    host = m.group(0).split("://", 1)[1].split("/", 1)[0]
    choices = [h for h in _FRESH_HOSTS if h != host]
    if not choices:
        return None
    new_text = _replace_url_host(text, choices[0])
    return (new_text, "fresh-lookalike-domain") if new_text else None


def _m_tld_swap(text: str) -> tuple[str, str] | None:
    """Same name, shadier TLD — tests TLD-reputation signals."""
    m = _URL_RE.search(text)
    if not m:
        return None
    host = m.group(0).split("://", 1)[1].split("/", 1)[0]
    swapped = re.sub(r"\.(com|net|org)$", ".xyz", host)
    if swapped == host:
        return None
    new_text = _replace_url_host(text, swapped)
    return (new_text, "tld-swap") if new_text else None


def _m_brand_subdomain(text: str) -> tuple[str, str] | None:
    """Real brand as a subdomain of the malicious domain — classic phish."""
    m = _URL_RE.search(text)
    if not m:
        return None
    host = m.group(0).split("://", 1)[1].split("/", 1)[0]
    if host.startswith("paypal.com."):
        return None
    new_text = _replace_url_host(text, f"paypal.com.{host}")
    return (new_text, "brand-as-subdomain") if new_text else None


def _m_urgency_rephrase(text: str) -> tuple[str, str] | None:
    """Same threats, different words — attacks keyword-based urgency."""
    for old, new in _URGENCY_SWAPS:
        if old in text:
            return text.replace(old, new, 1), "rephrased-urgency"
    return None


def _m_lure_rephrase(text: str) -> tuple[str, str] | None:
    """Same lure, different phrasing — attacks template matching."""
    for old, new in _LURE_SWAPS:
        if old in text:
            return text.replace(old, new, 1), "rephrased-lure"
    return None


def _m_restructure(text: str) -> tuple[str, str] | None:
    """Move the CTA above the threat — attacks positional heuristics."""
    paras = [p for p in text.split("\n\n") if p.strip()]
    cta_idx = next((i for i, p in enumerate(paras) if _URL_RE.search(p)), None)
    if cta_idx is None or cta_idx == 0:
        return None
    cta = paras.pop(cta_idx)
    paras.insert(0, cta)
    return "\n\n".join(paras), "restructured"


_MUTATORS = [
    _m_homoglyph_brand,
    _m_fresh_domain,
    _m_tld_swap,
    _m_brand_subdomain,
    _m_urgency_rephrase,
    _m_lure_rephrase,
    _m_restructure,
]


def mutate_with_axes(email_body: str, n: int = 5,
                      seed: int = 20261005) -> list[Mutation]:
    """Like mutate(), but each variant carries the axes that produced it."""
    rng = random.Random(seed)
    combos = [c for k in (2, 3)
              for c in itertools.combinations(range(len(_MUTATORS)), k)]
    rng.shuffle(combos)
    out: list[Mutation] = []
    for combo in combos:
        if len(out) >= n:
            break
        text, axes = email_body, []
        for i in combo:
            res = _MUTATORS[i](text)
            if res is None:
                break
            text, axis = res
            axes.append(axis)
        else:
            if text != email_body:
                out.append(Mutation(text=text, axes=axes))
    return out


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
                   fresh_variants: list[str] | list[Mutation] | None = None) -> RegressionReport:
    """Replay the corpus (+ any fresh variants) through the live pipeline.

    Fresh variants may be plain strings or Mutation objects (which carry
    their axes into the saved fixture). Misses are saved as new fixtures.
    """
    from ..orchestrator import analyze_email

    report = RegressionReport()
    cases = load_cases(corpus_dir)

    for i, variant in enumerate(fresh_variants or []):
        if isinstance(variant, Mutation):
            text, axes = variant.text, variant.axes
        else:
            text, axes = variant, []
        # Dedup: the engine is seeded, so re-runs produce identical texts.
        # Don't bank (or re-analyze) a variant the corpus already has.
        if any(c.variant == text for c in cases):
            continue
        case_id = _new_case_id(corpus_dir)
        res = analyze_email(case_id, text)
        case = RegressionCase(
            id=case_id, variant=text, expected_label="SCAM",
            actual_label=res.verdict.label.value, score=res.verdict.score,
            first_missed_at=datetime.now(timezone.utc).isoformat(),
            mutation_axes=axes,
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
