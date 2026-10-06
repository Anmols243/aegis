# AEGIS Build Plan — Oct 5 → Oct 10, 2026

Submission locks **Saturday Oct 10, 12:00 PM ET**. Work backwards from that. One phase = one goal; commit locally at each phase boundary.

## Build status — Oct 4 (evening)

All pipeline code is **implemented and offline-tested** (15 unit tests, 14 pass,
1 skipped pending Chromium download):
- ✅ triage, forensic analyst, arbiter, threat graph, verdict card, webhook
  receiver (HMAC), AgentBoxD reply/draft client, link sandbox (+SSRF guards),
  vision inspector (render path; LLM call needs `MODEL_VISION`), red-team
  mutate + regression harness, orchestrator wiring, n8n workflow, demo script.
- ⏳ **Live testing needs keys**: `FEATHERLESS_API_KEY`, `AGENTBOXD_API_KEY`,
  `AGENTBOXD_WEBHOOK_SECRET`, `MODEL_TRIAGE`, `MODEL_VISION` → then run
  `scripts/smoke_llm.py`, forward a real email, watch the verdict reply land.
- ⏳ Momen dashboard, demo video recording, Devpost submission.

## Day 0 — Today (Oct 4, remaining)

- [ ] Redeem sponsor codes (first-come-first-served): AgentBoxD (800), YouCam (1000), n8n (300), Kariaa (1000)
- [ ] Create the AgentBoxD inbox; note the address + API key
- [ ] Featherless: pick and verify model IDs in the playground — need one fast/cheap (triage), one long-context (forensic/red-team), one vision (Qwen-VL-class)
- [ ] Export keys: `FEATHERLESS_API_KEY`, `AGENTBOXD_API_KEY`, `AGENTBOXD_WEBHOOK_SECRET`, `MODEL_TRIAGE`, `MODEL_VISION`

## Phase 1 — Oct 5: Ingress + triage live

- FastAPI webhook receiver with HMAC verification (scaffolded; wire to real inbox)
- Triage agent against the real Featherless API — `python scripts/smoke_llm.py` must return valid entity JSON on a sample phish
- **Done when:** forwarding an email to the inbox produces a logged triage JSON in `data/`
- Commit

## Phase 2 — Oct 6: Forensic + arbiter → first end-to-end verdict

- Forensic analyst with evidence-cited findings
- Arbiter v1 (AgentBoxD scores + triage + forensic only; vision/sandbox weighted at 0 until they land)
- Verdict card renderer → reply sent via AgentBoxD
- **Done when:** a forwarded phishing email gets a verdict-card reply with cited evidence
- Commit

## Phase 3 — Oct 7: Vision inspector

- Playwright render + screenshot + vision-model brand-impersonation check
- Wire its signal into the arbiter at full weight
- **Done when:** a fake-brand login email is caught *by the vision signal* with the text signals neutralized (prove the modality adds value)
- Commit

## Phase 4 — Oct 8: Sandbox + threat graph

- Link sandbox with the full SSRF/timeout/no-JS contract
- Threat-graph store + campaign clustering over a seeded corpus (collect 10–15 real phishing samples during the week)
- Verdict card gains "part of campaign #N" linkage
- Commit

## Phase 5 — Oct 9: Red-team loop + dashboard

- Red-team mutator + regression harness; seed `tests/regression/` with first misses
- Momen dashboard: verdict feed + campaign graph + regression results
- Full dry-run of the demo arc (see `demo/DEMO_SCRIPT.md`)
- Commit

## Phase 6 — Oct 10 (morning): Ship

- Record 2–4 min demo video, upload to YouTube
- Polish README, screenshots, architecture diagram
- Push to GitHub, submit on Devpost before 12:00 PM ET
- Commit, tag `forgehacks-2026-submission`

## Cut list (if time runs short — cut in this order)

1. Dashboard polish → static screenshot export instead
2. n8n workflow → direct webhook is enough for the demo
3. Red-team mutation count → 3 variants instead of 10
4. Sandbox screenshot classification → URL reputation signals only

**Never cut:** evidence citations, the HMAC/SSRF security contracts, the end-to-end verdict reply. Those are the judging criteria.
