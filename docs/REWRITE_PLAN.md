# AEGIS v2 rewrite plan

Branch: `overhaul`. Deadline: Devpost locks Oct 10, 12:00 PM ET.

## Principle

New architecture, proven detection logic carried over. The 13 deterministic
signal checks, the evidence-grounding validator, the arbiter math and the
red-team mutation engine are tested and work; they get ported into the new
structure (and tested again), not reinvented. Everything around them
(service layout, storage, API, job handling, security, frontend) is rebuilt.

## Target architecture

```
frontend/  Next.js (App Router) + TypeScript + Tailwind + shadcn/ui
   │  same-origin proxy (/api/* -> backend), no open CORS
   ▼
backend/   FastAPI (async)
   api/v1      analyses · events (SSE) · campaigns · redteam · ingest · stats · health
   core/       settings (pydantic-settings, .env) · JSON logging · auth · errors
   pipeline/   Stage interface + DAG runner that emits progress events
               parse(.eml/MIME) → signals → triage → {forensic, vision, sandbox} → graph → arbiter → report
   providers/  LLM provider (Featherless, OpenAI-compatible, async, retries, JSON mode)
   storage/    SQLite via SQLAlchemy 2 async: analyses, stage_runs, findings,
               entities (campaign graph), jobs, deliveries (idempotency), audit
   workers/    DB-backed job queue + optional AgentBoxD poller
```

Ingestion channels: web (paste text / upload .eml), AgentBoxD webhook, AgentBoxD poller.
All three create the same `analysis` job; the frontend watches it live over SSE.

## Security fixes (from the Oct 6 review)

- No `Access-Control-Allow-Origin: *`; frontend reaches the API same-origin.
- Auth required whenever bound beyond localhost (API key, constant-time compare, header only, never in URLs).
- Webhook body limit enforced while streaming, before signature work.
- Sandbox SSRF: block every non-global address (`ipaddress.is_global`, covers 0.0.0.0, IPv4-mapped IPv6, CGNAT), follow redirects manually and check every hop, connect to the pre-checked IP (closes DNS rebinding).
- Job marked done only after success; failures retried with backoff.
- Pinned dependencies.

## New features (judge-facing)

1. **Analyze in the browser**: paste an email or drop a `.eml`; no inbox needed to try it.
2. **Live agent view**: each agent lights up as it runs (SSE), with timings.
3. **Evidence highlighting**: every finding's quoted excerpt is highlighted in the original email.
4. **Campaign graph**: interactive graph of emails linked by shared domains, senders, URLs, phones, templates.
5. **Red-team arena**: run a mutation round from the UI and watch which variants get caught.
6. **Shareable verdict page**: read-only link for a single verdict (to send to a family member).
7. **Landing page** explaining the system with the sonar-grid hero and live counters.

## Phases

| # | Phase | Verified by |
|---|---|---|
| 1 | Backend core: settings, logging, storage, LLM provider, pipeline runner, ported stages, security fixes | pytest (ported + new security tests) |
| 2 | API + jobs + SSE + ingestion (web, webhook, poller) | pytest API tests, curl smoke |
| 3 | Frontend scaffold + design system (lime HUD, sonar grid, border beam, dot pattern) + pages | typecheck, build, browser screenshots |
| 4 | Features: live agent view, evidence highlighting, campaign graph, red-team arena, share page | browser run against live backend with real Featherless calls |
| 5 | Eval re-run, docs (README, ARCHITECTURE, DECISIONS, LOG), demo script, adversarial review | eval numbers, fable-judge pass |

The old `src/aegis` tree stays until v2 passes phase 5, then is removed.

## Submission requirements (ForgeHacks participant packet)

Judged on 5 equal criteria: real-world impact, technical implementation & AI
use, innovation, execution & completeness, presentation. "Judges will test
what you submit"; "a half-working project is okay, overstating it isn't."

Devpost submission needs: what we built + problem, track (AI + Cybersecurity),
**demo video or live link**, code repo, **what works and what doesn't**.
Deliverables added to phase 5:

- Deployed live link (frontend + backend) so judges can try it without setup.
- README: problem, solution, impact, run instructions, honest works/doesn't-work list, AI-use note.
- Devpost write-up draft (`docs/DEVPOST.md`) and demo-video script (`demo/DEMO_SCRIPT.md`).
- Sponsor usage stated plainly (Featherless models, AgentBoxD inbox + scores; the
  AI + Cybersecurity track prize is AgentBoxD-sponsored).
