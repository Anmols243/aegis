# AEGIS — Multi-Agent Adversarial Scam Defense

**ForgeHacks 2026 · AI + Cybersecurity track**
*Track prompt: "Build an AI-powered solution that helps people recognize, prevent, verify, or respond to scams, impersonation, and fraud enabled by AI or modern technologies."*

Forward any suspicious email to AEGIS. A pipeline of specialist AI agents — triage, forensic analysis, visual brand-impersonation inspection, link sandboxing — dissects it, cross-references a threat-intelligence graph of known scam campaigns, and replies with an **evidence-cited verdict: SCAM / SUSPICIOUS / LIKELY SAFE**. A red-team agent continuously mutates real scams to probe the pipeline's blind spots; every miss becomes a permanent regression test.

## The problem

Phishing remains the #1 way people get compromised, and AI-generated lures are now hyper-personalized and visually convincing. Spam filters give a silent binary verdict — non-technical users never learn *why* something is a scam, so they stay vulnerable to the next variant.

## How it works

```
                    ┌─────────────┐
                    │  AgentBoxD  │  real inbox for the agent
                    │    inbox    │  + injection/phishing/auth scores
                    └──────┬──────┘
                           │ signed webhook (HMAC-SHA256)
                    ┌──────▼──────┐
                    │   FastAPI   │  /webhook/agentboxd
                    │  receiver   │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │ Orchestrator│
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Triage   │ │ Forensic │ │ Vision   │
        │ (fast)   │ │ (256K)   │ │ Inspector│
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             │            │            │
             │     ┌──────▼──────┐     │
             │     │Link Sandbox │     │
             │     └──────┬──────┘     │
              └────────────┼────────────┘
                           ▼
                    ┌──────────────┐
                    │ Threat graph │  campaign clustering
                    │  (networkx)  │
                    └──────┬───────┘
                           ▼
                    ┌──────────────┐
                    │   Arbiter    │  ensemble verdict + calibrated confidence
                    └──────┬───────┘
                           ▼
              ┌────────────────────────┐
              │ Verdict card → reply   │  via AgentBoxD
              │ Campaign dashboard     │  Momen
              └────────────────────────┘

   Offline loop: Red-team agent ──mutates──► pipeline ──miss──► tests/regression/
```

Every verdict cites its evidence: header lines, URLs, phrases, screenshots. No black boxes.

## Sponsor resources used

| Resource | Role in AEGIS |
|---|---|
| **AgentBoxD** | Real agent inbox; inbound injection/phishing/SPF-DKIM-DMARC scores used as *features*; signed webhooks; reply channel |
| **Featherless AI** | The entire agent ensemble — triage (fast model), forensic analyst (long-context), vision inspector (open vision model), red-team mutator |
| **n8n** | Webhook → pipeline → reply orchestration plumbing |
| **Momen** | Campaign-graph dashboard |
| **YouCam API** | Demo assets (verdict-card visuals, video thumbnails) |
| **DevSwarm** | Build tooling |

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in FEATHERLESS_API_KEY, AGENTBOXD_API_KEY, ...
# Phase 1 smoke test (no inbox needed):
python scripts/smoke_llm.py
# Webhook receiver:
uvicorn aegis.ingress.webhook:app --port 8000
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design and [BUILD_PLAN.md](BUILD_PLAN.md) for the day-by-day plan.

## Current status (Oct 4)

The full pipeline is implemented and offline-tested (`python -m unittest tests.test_offline` — 14 pass, 1 skipped pending Chromium download). Live end-to-end (forward email → verdict reply) needs the sponsor API keys in `.env` — see Day 0 checklist in BUILD_PLAN.md.

## What was built with AI (honesty note, per hackathon rules)

Built during the ForgeHacks window (Oct 3–10, 2026) with AI coding assistance (Claude Code / Muse). AgentBoxD, Featherless, n8n, Momen, and YouCam are third-party sponsor APIs used as infrastructure. All agent prompts, pipeline logic, threat-graph code, and evaluation are original to this project.

## Submission checklist

- [ ] Track selected: AI + Cybersecurity
- [ ] Demo video (2–4 min) on YouTube — see `demo/DEMO_SCRIPT.md`
- [ ] GitHub repo + this README
- [ ] Devpost writeup: problem, technical approach, impact
- [ ] Screenshots / architecture diagram / deployment link
