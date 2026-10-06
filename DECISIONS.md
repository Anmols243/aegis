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

## D8 (Oct 6, 2026): Mailbox access over IMAP with app passwords

- **Context:** Users want AEGIS to watch their inbox. Gmail OAuth in testing mode only admits listed
  test users, so judges could not connect their own accounts; Microsoft requires OAuth for Outlook.com.
- **Decision:** IMAP over TLS with app passwords (Gmail, Yahoo, iCloud, custom). Read-only fetch
  (`BODY.PEEK`), labels and flags only, new mail only. Outlook listed as unsupported with the reason.
- **Consequences:** Works with most providers without a cloud project. Credentials must be stored, so
  they are encrypted (D9). OAuth providers are future work.

## D9 (Oct 6, 2026): Private by default, unlisted not authenticated

- **Context:** The public deployment has no user accounts, yet pasted and mailbox emails are personal.
- **Decision:** A per-browser random viewer token (HttpOnly cookie via the proxy). Private analyses
  are listed only to their owner and otherwise reachable only by an unguessable id or share link.
  Cross-user threat intel is kept but anonymised. Content is purged after a retention period.
- **Consequences:** No login friction for judges. Clearing cookies loses the "mine" list (the
  analyses still exist until retention). Anyone holding a link can open that one analysis.

## D10 (Oct 6, 2026): Sign in with Google for Gmail (amends D8)

- **Context:** App passwords proved too hard in practice: Google hides them unless 2-Step
  Verification is on (a teammate's account showed "not available for your account").
- **Decision:** Add Sign in with Google (OAuth code flow with PKCE, `gmail.modify`, Gmail API) as the
  primary Gmail path; keep IMAP app passwords for Yahoo, iCloud, custom and as a Gmail fallback.
  Publish the OAuth app unverified rather than leave it in Testing, so any Google account (including
  judges) can sign in.
- **Consequences:** One click for users. Unverified apps show Google's warning screen and are capped
  at 100 users; verification of a restricted scope is out of reach for the hackathon. Pending
  sign-ins are kept in memory (single process).
- **Amendment (same day):** Google blocks sign-in inside apps' built-in browsers ("This browser or
  app may not be secure"), where a teammate runs AEGIS. Sign-in now opens in a new tab and may finish
  in another browser; the mailbox is attached to the starting session only after the user confirms a
  matching 4-digit code in the browser that holds the Google account. A sign-in link someone else
  started and sent to a victim would still need the victim to press "Codes match, connect" against a
  warning; that social-engineering risk is accepted and stated on the page.
