# Decisions

Append-only. A superseded decision gets a new entry; old entries are not rewritten.

## D1 (Oct 6, 2026): Rewrite v1 into separate backend and frontend apps

- **Context:** v1 was one FastAPI process with a single-file HTML dashboard, synchronous stages in
  threads, a JSON-file graph, and an LLM path that only worked inside one specific sandbox
  (a skill CLI). A security review found open CORS on an unauthenticated API and SSRF gaps.
- **Decision:** New `backend/` (async FastAPI, SQLite via SQLAlchemy, DB-backed queue, DAG runner,
  SSE) and `frontend/` (Next.js + TypeScript + Tailwind + shadcn). Proven detection logic (signal
  checks, grounding, arbiter math, mutation engine) is ported and re-tested, not reinvented. v1 is
  kept in `legacy/v1/`.
- **Consequences:** Two services to run. Judges can try it in a browser without an inbox.

## D2 (Oct 6, 2026): SQLite as both store and job queue

- **Context:** Hackathon scale, single machine, must survive restarts.
- **Decision:** The `analyses` table is the queue (status, attempts, next_attempt_at). No Redis.
- **Consequences:** One process only. Moving to Postgres + a real queue is the scale-out path.

## D3 (Oct 6, 2026): Corroboration rule in the arbiter

- **Context:** In v1 a confirmed phish scored 0.69 (SUSPICIOUS) because a dead phishing domain
  (sandbox "unreachable", 0.3) dragged the weighted mean down, and web submissions have no inbox
  provider score.
- **Decision:** Add deterministic signals as an arbiter input (noisy-OR risk) and a rule: two or
  more independent strong sources mean SCAM. One strong source alone is not enough.
- **Consequences:** 12/12 scams at SCAM and 10/10 legitimate emails cleared on the eval set.
  A single over-eager source cannot convict on its own.

## D4 (Oct 6, 2026): Business-email-compromise checks are deterministic

- **Context:** The CEO gift-card sample has no links, so only the AI analyst saw it (SUSPICIOUS).
- **Decision:** Add `check_bec`: executive title on free webmail (high), a request to buy or send
  gift cards plus codes (high), payment-detail change (medium), secrecy paired with a money request
  (medium). The gift-card check requires a request verb, so receipts that mention a gift card code
  do not fire.
- **Consequences:** The sample moved to SCAM 0.95 with two independent sources.

## D5 (Oct 6, 2026): Sandbox pins connections to the vetted IP

- **Context:** v1 checked DNS, then let the HTTP client resolve again (DNS rebinding window) and
  only checked the final URL after following redirects automatically.
- **Decision:** Resolve once, require every address to be `is_global` (unwrapping IPv4 inside IPv6),
  connect to that IP with Host header and SNI, follow redirects manually re-checking each hop.
- **Consequences:** Rebinding and redirect-to-internal are closed; covered by tests against a local server.

## D6 (Oct 6, 2026): Red-team mutations stay deterministic

- **Context:** LLM mutators refuse to write deployable phishing, and a judged demo must work every time.
- **Decision:** Seeded template mutations along ten named axes, generalised beyond PayPal.
  Mutators edit only the body (and the From header for spoofing), so headers stay parseable.
- **Consequences:** Reproducible rounds; the axes are finite, which the README states.

## D7 (Oct 6, 2026): Model prose is dash-free, evidence is verbatim

- **Decision:** `validate.prose()` normalises em and en dashes in model-written claims and summaries
  (house style). Quoted excerpts are never altered, because they must match the email to be
  grounded and highlighted.
