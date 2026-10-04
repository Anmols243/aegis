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
  - **Threat graph**: campaign view — "shares infrastructure with 4 earlier scams."
- Verdict card reply lands in the inbox: 🛑 SCAM, confidence bar, red flags,
  action plan.

## 1:30–2:20 — The red team attacks
- "Static detectors rot. So AEGIS attacks itself."
- Red-team agent generates 3 mutated variants (show the mutations).
- Run them through: 2 caught, 1 missed → the miss is saved to
  `tests/regression/` as a permanent test. Show the file appearing.

## 2:20–3:00 — Close
- Dashboard (Momen): campaign graph, verdict feed, regression board.
- "Every verdict cites its evidence. Every miss makes it stronger."
- End card: GitHub repo, track (AI + Cybersecurity), team.

## B-roll / assets
- YouCam API: generate the thumbnail + verdict-card header visuals.
- Screen-record everything at 1080p; no shaky-cam phone footage of a screen.
