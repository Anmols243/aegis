"""Vision inspector: render email HTML → screenshot → brand-impersonation check.

CONTRACT (Phase 3):
  inspect(html: str) -> VisionVerdict

Catches what text analysis misses: pixel-faithful clones of bank / PayPal /
corporate login pages hosted on lookalike domains.

Implementation notes:
- Playwright headless Chromium, viewport 1280x900, screenshot full page.
- Feed the PNG (base64) to MODEL_VISION with the prompt below.
- Never render with JS enabled on untrusted HTML if avoidable; screenshots
  of static render are enough for brand-impersonation detection.
"""
from __future__ import annotations

from dataclasses import dataclass, field

VISION_PROMPT = """You are AEGIS-Vision, a brand-impersonation detector.
This is a screenshot of an email's rendered HTML.

Answer ONLY valid JSON:
{
  "impersonated_brand": "brand name or null",
  "confidence": 0.0-1.0,
  "notable_regions": ["e.g. 'fake login form center', 'logo top-left'"],
  "reason": "one sentence"
}

A brand is impersonated when the layout, logo, colors, or wording mimic a
real company's login / security / billing page but the context is an email.
Marketing emails that merely mention a brand are NOT impersonation."""


@dataclass
class VisionVerdict:
    impersonated_brand: str | None = None
    confidence: float = 0.0
    notable_regions: list[str] = field(default_factory=list)
    reason: str = ""
    screenshot_path: str = ""

    @property
    def risk(self) -> float:
        """Normalized 0..1 signal for the arbiter."""
        return self.confidence if self.impersonated_brand else 0.0


def inspect(html: str) -> VisionVerdict:
    """Phase 3: Playwright render → screenshot → MODEL_VISION."""
    raise NotImplementedError("Phase 3 — see BUILD_PLAN.md")
