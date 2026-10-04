# AEGIS demo script — 2–4 minute video shot list

Total target: ~3:00. One continuous narrative: a scam arrives, the agents
dissect it, the red team attacks, the system learns.

## 0:00–0:20 — The problem
- Talking head or voiceover: "AI-generated phishing is now personalized and
  visually perfect. Spam filters stay silent. People stay vulnerable."
- Show a real-looking phishing email (the PayPal lure from the smoke test).

## 0:20–0:45 — Forward to AEGIS
- Forward the email to the AEGIS inbox (show the AgentBoxD address).
- Cut to terminal: webhook received, triage JSON streaming in.

## 0:45–1:30 — The agents dissect it
- Split-screen or quick cuts per agent:
  - **Forensic**: findings with quoted evidence ("reply-to vs from mismatch —
    'security@paypa1-secure.com'").
  - **Vision**: side-by-side — real PayPal login vs rendered email screenshot,
    impersonation flagged.
  - **Sandbox**: URL followed in isolation, credential-harvest page classified.
  - **Threat graph**: campaign view — a parcel-scam inbound links to 3 seeded
    earlier scams sharing the sender domain and callback phone
    (run `scripts/seed_campaign.py` first).
- Verdict card reply lands in the inbox: 🛑 SCAM, confidence bar, red flags,
  action plan.

## 1:30–2:20 — The red team attacks
- "Static detectors rot. So AEGIS attacks itself."
- The deterministic red-team engine mutates the phish 5 ways — homoglyph
  brand, fresh lookalike domain, TLD swap, rephrased threats (show the axes).
- Run them through: 0/5 reach SCAM — all land SUSPICIOUS at 0.69, one point
  under the line. Forensics scored ~0.97 on every variant: the detector wasn't
  fooled, the ensemble is conservative without the provider signal.
- All 5 misses are banked to `tests/regression/` as permanent tests. Show the
  files appearing. "Every miss makes it stronger — literally, as code."

## 2:20–3:00 — Close
- Case-file dashboard (`dashboard/index.html`): verdict stamp, evidence
  exhibits, agent votes, red-team table — all real run data.
- "Every verdict cites its evidence. Every miss makes it stronger."
- End card: GitHub repo, track (AI + Cybersecurity), team.

## B-roll / assets
- `dashboard/screenshot.png`: the dashboard render for thumbnails/Devpost.
- Screen-record everything at 1080p; no shaky-cam phone footage of a screen.
