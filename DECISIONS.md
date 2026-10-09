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

## D11 (Oct 6, 2026): Sign in with Google and Microsoft only (supersedes D8)

- **Context:** App passwords stayed the main source of friction (D10), and Outlook.com users had no
  path at all because Microsoft requires OAuth for IMAP. Yahoo requires Yahoo's approval before an
  app may request mail scopes, and iCloud offers no mail sign-in for third-party apps.
- **Decision:** Remove IMAP and app passwords entirely. Support exactly two providers through one
  shared PKCE flow (`providers/oauth.py`): Google (`gmail.modify`, Gmail API) and Microsoft
  (`offline_access Mail.ReadWrite User.Read`, Microsoft Graph, `common` tenant so personal and work
  accounts both work). Mail.ReadWrite is the narrowest Graph scope that can set categories and
  flags. Yahoo and iCloud users forward mail to the AEGIS inbox (AgentBoxD) or paste it. The
  built-in-browser pairing flow from D10 applies to both providers (`/connect?state=`).
- **Consequences:** No passwords are ever handled; a single sign-in for most users. Graph has no
  per-app revoke, so disconnecting a Microsoft mailbox deletes the token and points the user to
  https://account.live.com/consent/Manage. Microsoft rotates refresh tokens, so each refresh may
  rewrite the stored (encrypted) token. Existing IMAP mailboxes stop polling and ask the user to
  reconnect. Each deployment needs its redirect URI registered on both OAuth clients.

## D12 (Oct 8, 2026): Remove the mailbox sign-in UI; the live test inbox is the inbox demo

- **Decision:** The "Connect your inbox" page (`/inbox`), the sign-in confirm page (`/connect`),
  their components, the home-page section and the mailbox privacy promises are removed. The nav's
  Inbox link becomes Live (`/live`). The backend mailbox and OAuth routes stay, unused by the UI.
- **Context:** The user asked to remove the page. Google and Microsoft OAuth clients were never
  configured, so the page could not connect anything; the AgentBoxD test inbox on `/live` shows the
  same pipeline working on real mail with no sign-in.
- **Consequences:** Mail sent to the test inbox is shown publicly on `/live`, partially censored
  server-side (`services/livefeed.py`); the privacy page and README say so. Restoring mailbox
  sign-in means restoring the deleted pages from git history (commit before this change).

## D13 (Oct 10, 2026): Every case is private to the browser that made it; supersedes D12's public /live

- **Decision:** Test-inbox mail is tied to a browser by a personal code (`AEGIS-XXXXXX`, table
  `viewer_codes`, `services/claims.py`) in the subject or body. `/live` lists only the viewer's own
  mail; Cases lists the built-in samples plus the viewer's own analyses, nothing else. Mail without
  a known code is analyzed and replied to by email but listed for nobody. Default retention drops
  from 7 days to 1. `DELETE /history` erases everything a browser owns.
- **Context:** The user wants each visitor to see only their own tests once deployed, with nothing
  shown globally, and a way to wipe their history. Everyone mails one shared AgentBoxD address, so
  ownership needs a token the sender carries; a per-visitor temporary inbox was the alternative but
  needs a workspace-wide key and a poller rewrite, too risky on deadline day.
- **Consequences:** Anyone who learns a code can push mail into that browser's view (it cannot read
  anything). Public inbox rows from before this change no longer appear in Cases. AgentBoxD still
  keeps its own copy of received mail; the privacy page says so. Clearing cookies loses the code
  and the history with it.

## D14 (Oct 10, 2026): A coded email links its sender address to the browser

- **Decision:** When test-inbox mail carries a browser's code, the SHA-256 of its lower-cased sender
  address is linked to that browser (`sender_links`). Later mail from that address is owned by
  the same browser without a code. The latest coded email wins; "Delete my history" drops the link.
- **Context:** Mail written by hand (not through the Mail app button) never had the code, so it was
  fetched and answered but never shown; users read that as "not fetching".
- **Consequences:** The From header can be forged, so anyone who forges a linked address can push
  mail into that browser's view (they still cannot read anything). Mail sent before the first
  coded email stays unowned.
