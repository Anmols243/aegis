# Log

Newest first.

## 2026-10-06: Sign in with Google for Gmail

- **Changed:** `providers/google.py` (OAuth + PKCE, Gmail history polling, labels, revoke),
  `/oauth/google/start` and `/oauth/google/callback`, Google-first connect form on `/inbox` with app
  passwords behind a toggle, privacy copy. See DECISIONS.md D10.
- **Why:** Google refused to show app passwords for a teammate's account; app passwords were too much
  friction.
- **Verified:** 82 backend tests pass (fake Google API: state bound to browser and single use, PKCE,
  scope check, new-mail-only cursor, sent mail skipped, label + star, encrypted token, revoke on
  disconnect). Mutation check: breaking each of those 7 guards fails a test. Browser: button opens
  accounts.google.com with the right parameters; cancel returns to `/inbox` with a toast.
- **Not verified:** a full consent with a real OAuth client (needs the Google Cloud setup in README).
- **Follow-up:** sign-in from an app's built-in browser. Google opens in a new tab; if it returns to
  another browser, `/connect/google` asks to confirm a 4-digit code shown in both windows, and the
  starting window updates by polling. 84 tests; mutation check: 10 guards, all caught. Browser: two
  isolated sessions against a fake Google showed matching codes, the confirm page, the panel
  connecting by itself and the other browser getting nothing; disconnect cleaned up.

## 2026-10-06: Mailbox connection and privacy (v2.1)

- **Changed:** Connect an IMAP mailbox (Gmail, Yahoo, iCloud, custom) with an app password; new mail
  is analyzed and tagged `AEGIS/Scam` or `AEGIS/Suspicious`. Privacy model: per-browser viewer cookie,
  private-by-default analyses, anonymised cross-user relations, AES-256-GCM credentials, owner
  address redaction, retention purge, disconnect-and-delete. See DECISIONS.md D8, D9.
- **Verified:** 78 backend tests pass (fake IMAP server for connect, poll, label, disconnect;
  visibility, redaction, retention, encryption). Mutation check: disabling private-list filtering,
  related redaction, owner redaction, the mailbox owner check or the purge each fails a test.
  Live backend migrated the existing database in place.
- **Not verified:** a real Gmail/Yahoo/iCloud mailbox (needs a test account and app password).
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
