"""Vision inspector: render email HTML → screenshot → brand-impersonation check.

Catches what text analysis misses: pixel-faithful clones of bank / PayPal /
corporate login pages hosted on lookalike domains.

Safety: Chromium runs with JavaScript DISABLED — the screenshot is a static
render, which is all brand-impersonation detection needs.
"""
from __future__ import annotations

import base64
import os
import tempfile
from dataclasses import dataclass, field

from ..config import get_settings
from ..llm import chat_json

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


def _launch_browser(p):
    """Default headless-shell launch, falling back to the full Chromium build
    (some installs only fetch one of the two)."""
    try:
        return p.chromium.launch()
    except Exception:
        import glob
        cands = sorted(glob.glob(os.path.expanduser(
            "~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome")))
        if not cands:
            raise
        return p.chromium.launch(executable_path=cands[0])


def render_html(html: str, out_path: str | None = None) -> str:
    """Static render of untrusted HTML → PNG screenshot. No JavaScript."""
    from playwright.sync_api import sync_playwright

    path = out_path or tempfile.mktemp(suffix=".png")
    with sync_playwright() as p:
        browser = _launch_browser(p)
        ctx = browser.new_context(
            java_script_enabled=False,
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()
        page.set_content(html, wait_until="domcontentloaded")
        page.screenshot(path=path, full_page=True)
        browser.close()
    return path


def inspect(html: str) -> VisionVerdict:
    """Full pipeline: render → vision model → structured verdict."""
    shot = render_html(html)
    with open(shot, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    model = get_settings().model_vision
    data = chat_json(
        model,
        [
            {"role": "system", "content": VISION_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": "Screenshot of the rendered email:"},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ]},
        ],
    )
    return VisionVerdict(
        impersonated_brand=data.get("impersonated_brand"),
        confidence=float(data.get("confidence", 0.0)),
        notable_regions=data.get("notable_regions", []),
        reason=data.get("reason", ""),
        screenshot_path=shot,
    )


if __name__ == "__main__":  # quick manual check: render only, no LLM
    sample = ("<html><body style='font-family:sans-serif'>"
              "<h1 style='color:#003087'>PayPal</h1>"
              "<p>Verify your account:</p>"
              "<form><input type='password' placeholder='Password'></form>"
              "</body></html>")
    print("screenshot:", render_html(sample, "/tmp/aegis_vision_sample.png"))
