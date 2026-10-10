# AEGIS architecture (v2)

## Principles

1. **Evidence, not vibes.** Every claim cites the artifact it came from, and the citation is checked
   in code (`pipeline/validate.py: grounded`). Fabricated quotes are dropped, not rendered.
2. **Specialists, not a chatbot.** Each stage has a narrow contract and structured, validated output.
   The LLM is a component inside a system.
3. **Measure what can be measured.** Deterministic checks (`pipeline/signals.py`) produce facts the
   AI reasons over instead of re-deriving them.
4. **Fail closed.** A failed or missing stage pushes toward SUSPICIOUS, never toward safe.
5. **Hostile input everywhere.** Email bodies, links, HTML and model output are all untrusted.

## Layout

```
backend/aegis/
  main.py            app factory, lifespan (DB, workers, optional poller), middleware
  api/routes.py      HTTP API v1 (contract: docs/API.md), SSE progress stream
  core/              settings, JSON logging, event bus, security (auth, rate limit, body limit, headers)
  db/                SQLAlchemy 2 async models + session (SQLite, WAL)
  providers/         llm.py (Featherless), agentboxd.py (inbox API, HMAC), oauth.py (PKCE sign-in), google.py (Gmail API), microsoft.py (Graph)
  pipeline/          parse, triage, signals, forensic, vision, sandbox, graph, arbiter, report, runner
  services/          analysis lifecycle, campaigns graph, red team, samples, abuse report
  workers/           DB-backed job queue, AgentBoxD poller
frontend/            Next.js App Router + TypeScript + Tailwind + shadcn/ui
  app/api/[...path]  same-origin proxy to the backend; adds the API key server-side
legacy/v1/           the original single-process pipeline and dashboard (Oct 3 to 5)
```

## Request flow

1. **Ingest.** `POST /api/v1/analyses` (paste, `.eml`, sample), the AgentBoxD webhook
   (HMAC-SHA256 verified, idempotent via a unique `external_id`), or the poller. Each creates a row
   in `analyses` with status `queued` and nine `stage_runs` rows in `pending`.
2. **Queue.** `workers/queue.py` claims the oldest queued row. Crash-safe: rows left `running` are
   re-queued on startup; failures retry with exponential backoff up to `MAX_ATTEMPTS`; a row is
   `done` only after the result is stored.
3. **Pipeline.** `pipeline/runner.py` runs a dependency graph. Every stage starts as soon as its
   inputs exist, so forensic, vision, sandbox and graph run concurrently. Each state change is written
   to `stage_runs` and published on the in-process event bus.
4. **Live view.** `GET /analyses/{id}/events` (SSE) replays recorded stage events, then streams live
   ones until `done`. The frontend draws the agents lighting up.
5. **Reply.** For inbox mail, the verdict card is replied in-thread through AgentBoxD.

## Stages

| Stage | Depends on | Notes |
|---|---|---|
| parse | | stdlib `email` parser; pasted header blocks, multipart, HTML-only mail |
| triage | parse | LLM extraction merged with regex extraction; LLM down means deterministic only (`degraded`) |
| signals | triage | 15 pure checks; noisy-OR risk (one high signal 0.6, two 0.84) |
| forensic | signals | Findings must quote the email; ungrounded quotes dropped; risk clamped to [0, 1] |
| vision | parse | Chromium with JavaScript off and every request except `data:`/`blob:` aborted; own thread and event loop |
| sandbox | triage | See SSRF section |
| graph | triage | Stores indicators, links to earlier emails |
| arbiter | all of the above | See below |
| report | arbiter | Red flags, tailored next steps, verdict card markdown |

Essential stages are parse, arbiter and report. Any other stage can fail or be skipped; its signal is
then missing and the arbiter compensates.

## Arbiter

- Weighted mean over present signals, weights renormalised: forensic 0.25, signals 0.35,
  sandbox 0.15, vision 0.15, AgentBoxD phishing score 0.10.
- Thresholds: SCAM at 0.65 or above, SUSPICIOUS at 0.35 or above, else LIKELY SAFE.
- **Corroboration:** if two or more independent sources report strong evidence (forensic risk 0.85
  or more, a high-severity deterministic signal, a credential-harvest or malware page, visual brand
  impersonation at 0.7 or more, AgentBoxD phishing 0.85 or more), the label is SCAM. A dead phishing
  domain (sandbox "unreachable") cannot drag a doubly-confirmed scam down to SUSPICIOUS.
- **Fail closed:** without the forensic analyst, never LIKELY SAFE. A missing model risk score
  fails validation. The forensic stage retries invalid JSON or scores once with explicit format
  instructions and validates the replacement, including evidence grounding. Two invalid replies
  leave the stage failed. One strong source sets a SUSPICIOUS minimum even when the mean is lower.
- **Forensic output format:** the provider receives a JSON schema requiring a numeric `risk_score`
  in the range 0 to 1, findings with evidence, techniques and summary. Local validation and evidence
  grounding still run after generation.
- **Microsoft billing:** legitimate Microsoft subdomains and Azure portal links do not count as
  sender spoofing merely because their hostnames differ. This does not clear the email by itself.
  The sandbox does not classify a password form on the exact HTTPS Microsoft sign-in hosts as
  credential theft when every form targets those hosts. Lookalikes, external form destinations,
  malware downloads and other email evidence retain their checks.
- "Confidence" is the distance from the nearest threshold. It is a heuristic and is never presented
  as a calibrated probability.

## Campaign graph

Indicators per analysis (`entities` table): sender address, domain, URL (host + path), phone digits,
and a template fingerprint (body with URLs, emails and digits masked). Two emails are related when they
share indicators: high if they share two strong kinds (sender, domain, phone) or four indicators,
medium if one strong kind or two indicators, otherwise weak. Campaigns are connected groups of
flagged emails (SCAM or SUSPICIOUS) joined by medium or high links. Free-webmail domains never count
as shared infrastructure. Red-team variants stay out of the graph.

## Security

- **SSRF (link sandbox).** Only http/https; no userinfo in URLs. The host is resolved once and every
  address must be globally routable (`is_global`), which rejects loopback, private, link-local,
  CGNAT, 0.0.0.0, multicast and IPv4 smuggled inside IPv6 (mapped, 6to4, NAT64, Teredo). The
  connection goes to the exact IP that passed (Host header and TLS SNI carry the name), which
  closes DNS rebinding. Redirects are followed manually and every hop is re-checked. 8 s timeout,
  512 KB cap, no JavaScript, no cookies, no form submission.
- **Renderer isolation (vision).** JavaScript disabled, default-deny network, 2 MB HTML cap, bounded
  render time, browser closed on every path.
- **API.** Optional bearer API key (constant-time compare, header only, never URLs). No CORS unless
  allowlisted. Request bodies limited while streaming (before parsing or signature work). Per-client
  token-bucket rate limits (stricter on submissions). Strict security headers. The frontend proxy
  holds the key server-side.
- **Webhook.** HMAC-SHA256 over the raw body, constant-time compare, 401 and audit log on mismatch,
  idempotent on message id.
- **Prompt injection.** Email content is wrapped in `<UNTRUSTED_EMAIL>` delimiters (a forged closing
  tag inside the email is neutralised), the system prompts forbid following embedded instructions,
  and attempts to instruct the AI are reported as findings. The red team includes a prompt-injection
  mutation axis.
- **Model output.** Treated as untrusted: JSON validated, scores clamped or rejected, lists capped,
  evidence grounded, prose sanitised. Authorization is never decided by model output.
- **Share links.** Unguessable tokens; the public view omits the email body, entities and the reply card.

## Privacy model and mailboxes

- **Viewers.** The Next.js proxy gives each browser a random token in an HttpOnly, SameSite=Lax
  cookie and forwards it as `X-Aegis-Viewer`; the backend stores only its SHA-256 hash
  (`core/viewer.py`). It is the only cookie.
- **Visibility.** Samples and red-team variants are public. Pasted, uploaded, mailbox and
  inbox-forwarded mail is private: never listed except to its owner, opened only by its unguessable
  id (64-bit random) or share link. Campaign grouping still uses private mail (better threat intel),
  but other viewers see only `{"private": true, strength, why}` for it and a `hidden_count`.
  The stored campaign note never quotes another email's subject. Test-inbox mail is public only
  while `INBOX_PUBLIC=true`; on a start without it, such rows are made private again, so a
  tester's own address never stays on everyone's campaign graph.
- **Test-inbox ownership** (`services/claims.py`). Everyone mails one AgentBoxD address, so each
  viewer gets a code (`AEGIS-XXXXXX`, table `viewer_codes`) that `/live` puts in the subject of a
  prefilled message. Mail carrying it is owned by that viewer, and the SHA-256 of its lower-cased
  sender address is linked to the viewer (`sender_links`), so later mail from that address needs
  no code. Mail with neither is analyzed and replied to but owned by nobody, so listed nowhere.
  `/inbox/live` returns only the viewer's own mail; the stored `subject` drops the code. A forged
  From header can push mail into a linked viewer's list, never read from it.
- **Delete my history** (`DELETE /api/v1/history`). Hard-deletes every analysis the viewer owns
  (rows, stage runs, entities, screenshots) and its sender links.
- **Mailboxes** (`services/mailboxes.py`, `workers/mailbox.py`). Only Sign in with Google and Sign
  in with Microsoft; IMAP and app passwords were removed (DECISIONS D11). Only the refresh token is
  stored, encrypted with AES-256-GCM (`core/crypto.py`), associated data = mailbox id; access tokens
  stay in memory. Polling reads new mail only from a per-provider cursor (`Mailbox.last_uid`),
  downloads the raw MIME (never marked read), replaces the owner's address with `[your address]`
  before the email is stored or analyzed, and de-duplicates by
  `external_id = oa:{mailbox_id}:{message_id}`. After a verdict, SCAM gets a label plus a star or
  flag and SUSPICIOUS a label. A provider with no client id and secret configured is hidden.
- **Sign-in flow** (`providers/oauth.py`, shared). Authorization code flow with PKCE (S256) and a
  one-time `state` bound to the viewer that started it (in memory, 10 minutes, single process).
  Status moves `pending, exchanging` then `connected` (same browser) or `confirm, saving, connected`
  (other browser), or `cancelled` / `error`. A consent without the mail scope is refused. Microsoft
  rotates refresh tokens; the new one is re-encrypted on each refresh. The callback goes through the
  Next.js proxy so the viewer cookie applies.
- **Google** (`providers/google.py`). Scope `gmail.modify` only. The cursor is the Gmail
  `historyId` at sign-in; polling reads `history.list` (messageAdded, INBOX, sent and drafts
  skipped), fetches `format=raw`, and labels with `messages.modify` (`AEGIS/Scam` + STARRED,
  `AEGIS/Suspicious`). An expired history id restarts at "now". Disconnect revokes the token at
  Google.
- **Microsoft** (`providers/microsoft.py`, Graph v1.0, `common` tenant). Scopes `offline_access
  Mail.ReadWrite User.Read`; Mail.ReadWrite is the narrowest scope that can set categories. The
  cursor is the received time (epoch seconds) at sign-in; polling lists inbox messages with
  `receivedDateTime ge` (drafts skipped), de-duplicates same-second messages by id, and fetches
  `/messages/{id}/$value`. Tagging adds category `AEGIS/Scam` (+ flagged) or `AEGIS/Suspicious` and
  keeps existing categories. Graph has no per-app revoke, so disconnect deletes the token and the
  UI links to https://account.live.com/consent/Manage.
- **Sign-in from an app's built-in browser.** Google refuses to sign in inside embedded browsers, so
  "Continue with" is a plain link that opens a new tab (hosts hand it to the system browser; a
  copy-link fallback covers the rest). If the provider returns to the browser that started, the
  mailbox connects at once. If it returns to a different browser, the tokens are held in memory and
  that browser shows `/connect?state=` with the email and a 4-digit pairing code that the starting
  window also shows; only an explicit "Codes match, connect" attaches the mailbox to the session that
  started (never to the confirming browser). Cancel revokes the token (Google). The starting window
  polls `/oauth/status` and updates by itself.
- **Retention** (`services/analysis.py: purge_expired`, hourly). Private analyses older than their
  retention (mailbox setting, else `PRIVATE_RETENTION_DAYS`, default 1) lose raw message, body, quoted evidence,
  entities of legitimate mail, link details, AI summary, reply card and screenshot; the verdict stays.

## Storage

One SQLite file (`DATABASE_URL`), WAL mode: `analyses` (also the job queue), `stage_runs`,
`entities`, `redteam_runs`, `viewer_codes`, `sender_links`, `audit_events`. Screenshots in
`DATA_DIR/screenshots/`.

## Known limits

Single process (queue, event bus and rate limits are in-process), so scale out means moving the
queue and bus to Redis or Postgres. The sandbox cannot see JavaScript-built pages. Attachments are
checked by name and type only.
