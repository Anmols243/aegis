# Log

Newest first.

## 2026-10-06: v2 rewrite (branch `overhaul`)

- **Changed:** New `backend/` (FastAPI async, SQLite queue, DAG pipeline with SSE progress, Featherless
  provider, AgentBoxD webhook + poller) and `frontend/` (Next.js: landing, analyze, live case view with
  highlighted evidence, cases feed, campaign graph, red-team arena, share page). v1 moved to `legacy/v1/`.
  New: BEC checks, corroboration rule, hardened SSRF sandbox, API-key auth, streaming body limits,
  rate limits, share links, abuse reports, built-in samples, live eval script.
- **Why:** The v1 security review (open CORS on an unauthenticated API, SSRF bypasses, late body-size
  check) and a full overhaul requested for the hackathon submission. See DECISIONS.md D1 to D7.
- **Verified:** 70 backend tests pass (SSRF against a local server, webhook HMAC + idempotency, auth,
  limits, API end to end with a fake model). Live eval with real models: 22/22 correct, 0 false
  positives, 15 s mean (eval/RESULTS.md). Frontend `npm run build`, `tsc` and lint clean; every page
  screenshot-checked at 1440 and 390 px against the live backend; `.eml` upload through the proxy
  gave SCAM on a Netflix lookalike.
- **Not verified:** live AgentBoxD webhook and auto-reply in v2; Docker image build.

## 2026-10-06: v1 dashboard tweaks (before the rewrite)

- Sonar-grid background, HUD panels, border beam, dot pattern, filter chip contrast, scroll-bar
  clipping, `/sonar-grid.js` rate-limit exemption. Superseded by the v2 frontend.
