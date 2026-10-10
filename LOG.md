# Log

Newest first.

## 2026-10-10: Recover from missing provider completion choices

- **Observed:** deployed case `a_1a124a7f818ca85c9e8050cff44` failed forensic analysis with
  `TypeError: 'NoneType' object is not subscriptable`. The client indexed provider choices
  without validating them, which bypassed the forensic stage's invalid-output retry.
- **Fixed:** missing or empty choices and absent completion text now raise `LLMBadOutput`,
  allowing the bounded forensic retry. The completion after a token-budget retry is validated
  too. No risk score is invented when the provider fails.
- **Verified:** 131 backend tests passed, including reproducing the exact null-choices error,
  recovery through the real LLM client and forensic stage, and malformed token-retry output.
- **Limit:** no provider payload or server traceback was available; null choices reproduce
  the stored error, but the upstream reason for the incomplete response is unconfirmed.

## 2026-10-10: Recover from malformed forensic model responses

- **Fixed:** invalid JSON or a missing, nonnumeric or out-of-range `risk_score` immediately
  failed the forensic stage. It now retries once with explicit format instructions and
  revalidates the score and quoted evidence. A second invalid response still fails closed.
- **Changed:** the forensic prompt uses valid JSON as its format example and explicitly requires
  a numeric score from 0 to 1. Recovered responses are identified in the stage summary.
- **Verified:** 126 backend tests passed. New regressions cover recovery from four malformed
  response shapes, grounding after recovery, and failure after two invalid replies.
- **Limit:** the original live model response was not available; recovery was checked with
  controlled model responses through the real forensic stage and runner.

## 2026-10-10: Azure invoice false positives and unsafe verdict averaging

- **Fixed:** legitimate Microsoft sender subdomains and Microsoft-to-Azure portal links triggered
  spoofing and sender-link mismatch signals. Domain matching now respects label boundaries and
  the Microsoft service family; lookalikes and external invoice links remain flagged.
- **Fixed:** a single strong fraud source could be averaged down to LIKELY_SAFE by quiet stages.
  It now sets a SUSPICIOUS minimum; two corroborating sources still produce SCAM. A missing
  forensic risk score fails validation instead of defaulting to zero.
- **Fixed:** password forms on exact HTTPS `login.microsoftonline.com` and `login.live.com`
  endpoints were classified as credential theft. The exception checks all form destinations
  and does not apply to lookalikes, HTTP, tenant domains or malware downloads.
- **Verified:** 121 backend tests passed with `../.venv/Scripts/python -m pytest -q -p no:logging`
  from `backend/`. New regressions failed before their fixes. The user's original Azure bill and
  scam email were unavailable, so their exact live verdicts have not been reproduced.

## 2026-10-10: Gmail sign-in popup, equal-height panels

- **Fixed:** closing the Google sign-in left "Connect Gmail" spinning forever. Sign-in now opens in
  a popup; if it closes without a connected Gmail the button shows "Connection failed" for 2
  seconds, then "Connect Gmail" again. On success the popup posts back and closes itself; popups
  blocked fall back to same-tab sign-in, and Back from Google also resets the button.
- **Changed:** side-by-side panels end at the same height: Analyze (form grows, textarea fills),
  Campaigns (list no longer sticky/short), Red Team (a Results panel fills the left column until a
  round runs).
- **Verified:** `tsc`, `lint`, `next build`; in a browser, closing the popup logged "Waiting for
  Google" then "Connection failed" (1.2 s) then "Connect Gmail" (2 s later); column heights equal
  on all three pages (676, 706, 843 px pairs). Google client accepted (sign-in page loads).

## 2026-10-10: Gmail connect is back as the Inbox tab (D15)

- **Merged:** `saqib-gmail-inbox` (Saqib's Gmail inbox UI) into main, then rebuilt the page on the
  site's components (`gmail-inbox.tsx`): PageHero with Connect, Check now and Disconnect; message
  list beside the full verdict; refresh every 3 seconds; detail polls while the agents run.
- **Fixed from the branch:** `deleteHistory` defined twice in `api.ts`; Disconnect parsed an empty
  204 as JSON and reported failure; no auto-refresh; a nested `<main>`; 7 day retention instead of
  the site's 24 hours; no handling when Google sign-in is not configured; lint error
  (setState in effect). Restored `/connect` (the callback redirects there when sign-in returns to
  another browser). Server mailbox checks every 10 seconds (was 60).
- **Verified:** 106 backend tests; `tsc`, `lint`, `next build` clean; `/inbox` and `/connect`
  screenshots. Not tested: a real Google sign-in (no OAuth client configured on this machine).

## 2026-10-10: Live "Test the system" hero, one page hero site-wide, copy refresh

- **Changed (Live):** the address bar (address, Copy, code chip, two lines of rules) is replaced by a
  "Test the system" hero: status, three steps, and "Send a test email", which opens the mail app
  with the address, subject code and a body line filled in. A Gmail button opens Gmail's web
  compose (`mail.google.com/mail/u/0/?to&su&body&tf=cm`, desktop only: mobile browsers open the
  inbox instead). The panels now end 2rem above the viewport edge.
- **Added:** `PageHero` and `.hud-glow` (brand.md), used for the header of Analyze, Cases,
  Campaigns, Red Team, Privacy, Live, case detail and the shared verdict.
- **Changed (backend):** the stored `subject` of inbox mail drops the routing code, so lists read
  "sda", not "sda AEGIS-W5ZM4R"; the email keeps it.
- **Fixed (privacy):** one Oct 8 inbox row was still public, which put a tester's own address on
  everyone's Campaigns page. On start without `INBOX_PUBLIC`, public inbox rows go private.
- **Copy:** Cases no longer says cases are "deleted after 24 hours" (only email text is); Privacy
  lists "Delete my history"; home says "Browse cases" and that forwarded mail gets its verdict by
  email; the verdict note no longer mentions a public feed; README and ARCHITECTURE match.
- **Verified:** 106 backend tests (new: code stripped from subjects, startup un-publish);
  `tsc`, `lint`, `next build` clean; screenshots of all eight pages at 1440x900, Live at 1024 and
  390, Cases and a case at 390; no horizontal scroll anywhere; the anonymous campaigns API no longer
  contains the address. Not tested: clicking the Gmail button in a signed-in browser.

## 2026-10-10: Forensic stage failing on cut-off model replies

- **Fixed:** a reply stopped by `max_tokens` (Kimi-K3 can spend the budget reasoning) failed the
  stage with "no JSON object in model output". `LLMClient.chat` now retries once with double the
  budget when `finish_reason` is `length`. Also seen in the same reply: `PayPal\'s`, an escape
  strict JSON rejects; `parse_json_object` now accepts it (a literal backslash pair is left alone).
- **Verified:** 104 backend tests (new: apostrophe escape, retry on cut-off); edge cases with real
  backslashes parse unchanged. Seen once in 16 forensic runs; not reproduced live.

## 2026-10-10: Sender linking for test-inbox mail (D14)

- **Why:** hand-written mail (not sent via the Mail app button) lacked the code, so it was fetched
  and replied to but shown to nobody.
- **Changed:** a coded email links its sender address (hashed) to the browser; later mail from that
  address shows up without a code. Wiping history removes the link. Live and privacy copy updated.
- **Verified:** 102 backend tests (new: link learned, case-insensitive address, stranger stays
  unowned, wipe forgets the link); frontend `tsc`, `lint` and `next build` clean.

## 2026-10-10: Per-browser privacy, personal inbox codes, Delete my history (D13)

- **Changed:** every case is visible only to the browser that made it. Test-inbox mail is tied to a
  browser by a personal code (`AEGIS-XXXXXX`) in the subject (`services/claims.py`, table
  `viewer_codes`); `/live` shows the code, the Mail app button adds it. Mail without a known code is
  answered by email but listed for nobody. Cases: built-in samples plus the viewer's own only.
- **Added:** `DELETE /api/v1/history` and a "Delete my history" button on Cases (with confirm).
- **Changed:** default retention 7 days to 1. Privacy page, README, `docs/API.md` updated.
- **Removed:** the censored test-inbox section added to Cases earlier today (owned mail now comes
  through the normal list).
- **Verified:** 101 backend tests (new: per-browser feed, code matching, wipe only touches own
  rows); `tsc`, `lint`, `next build` clean; browser check of `/live` (code shown) and `/cases`
  (samples only, delete button). A real email carrying a code was not sent in this session.

## 2026-10-10: Poller spin fix, startup backfill, test inbox mail in Cases

- **Fixed (poller):** after the first email the poller looped forever. It set `since` from the
  message's `received_at`, but AgentBoxD filters on `created_at` (a few ms later), so the same
  message came back; the "same message" branch stepped 1 ms forward and the next pass reset `since`
  to `received_at` again. Each pass was an API call, so it spent the key's 120 requests/min and
  every later poll got 429: new mail never arrived. `since` now follows `created_at` and never moves
  back (`_advance`). Any other backend still running the old code drains its key the same way.
- **Added:** `AGENTBOXD_BACKFILL_S` (default 0): on startup also take mail from that many seconds
  back; already analyzed mail is skipped by `external_id`.
- **Corrected:** held mail is readable with `include_unscreened` (the full body comes back), so
  `messages:release` is not needed; the earlier "held mail is the cause" note was wrong.
- **Verified:** 101 tests pass (run from the repo root; with a `backend/.env` present, two config
  tests read it and fail). Live: the missed "anmol" email was backfilled, analyzed and replied to;
  the key's remaining quota stayed flat afterwards (no spin).
- **Added (frontend):** Cases lists finished test-inbox emails, censored as on `/live` (data from
  `/inbox/live`, no backend or privacy change). They link to `/live?email=<key>`, which pins that
  email. Public inbox mail is skipped there since it already appears in the regular list.
- **Verified:** `tsc`, `lint`, `next build` pass; `/live?email=<key>` opens the pinned email in a
  browser. The Cases row was not seen rendered: the local DB has no private inbox mail yet.

## 2026-10-09: Review fixes (sandbox stall, polling, races), vision skip, hero button

- **Fixed (security):** `sandbox.classify_html` used backtracking regexes on the fetched page. A
  512 KB page of repeated `<form>`, `<input `, `<a ` or `<title>` ran for minutes, and since it runs
  on the event loop one malicious link froze the whole server. Rewritten as linear scans (one tag
  pass, `find` for the title). Same results as the old code on 11 realistic pages; the adversarial
  pages now take under 0.15 s. Tests cover behaviour and a time bound (the old code still hung past
  40 s on the `<title>` case).
- **Fixed:** vision skips with "screenshot browser not installed on this server" instead of failing
  when Playwright's Chromium is missing (seen on another deployment); test added.
- **Fixed (frontend):** cases "load more" no longer appends results from a previous filter
  (generation ref); retry clears the old error; `/live` dissection and the red-team arena stop
  polling on 404.
- **Changed:** home hero button reads "Test system" (commit 43e43f9).
- **Not fixed, by choice:** detail endpoints open private analyses by id without an ownership check
  (by design, D9); open API without `AEGIS_API_KEY` (deployment setting); poller can skip a second
  mail received in the same millisecond (rare; a proper fix needs an AgentBoxD list call, not worth
  the risk before the deadline); `/stats` loads all rows (fine at demo scale).
- **Verified:** pytest 100 passed. tsc, eslint, build. Frontend fixes not exercised in a browser.

## 2026-10-08: /live fits one screen; mailbox sign-in UI removed (D12)

- **Changed:** `components/aegis/live-inbox.tsx` rebuilt for no long scroll: one-line address bar
  (Listening, address, Copy, Mail app, one line of help), then a fixed-height workspace
  (`lg:h-[calc(100dvh-17rem)]`) with the inbox feed and the dissection side by side, each scrolling
  inside its panel. The dissection keeps a verdict strip on top (risk number, label, plain verdict,
  stage bar) and puts the rest in tabs: Overview (summary, corroboration, next steps), Red flags,
  Agents (per-stage status, timing, summary or error) and Email (censored). It opens on Agents while
  the pipeline runs and on Overview once there is a verdict. `/live` header shortened.
  `PipelineView` is back to its original form (the `narrow` option is no longer used).
- **Removed (user request):** `/inbox` and `/connect` pages, `inbox-connect.tsx`,
  `signin-confirm.tsx`, the home "connect your inbox" section, the mailbox privacy promises
  (`privacy-promises.tsx` is now `private-badge.tsx` with only `PrivateBadge`), the mailbox and
  sign-in client functions and types in `lib/api.ts`. Nav "Inbox" is now "Live". Privacy page,
  README and cases empty state no longer describe mailbox sign-in; the privacy page and README now
  say the test inbox is public and censored. Backend mailbox and OAuth routes are untouched.
- **Verified:** tsc, eslint, build (route list has /live, no /inbox or /connect; both now 404).
  `agent-browser` failed to reach its own daemon (os error 10060, also after killing it), so
  screenshots were taken with the backend venv's headless Chromium: 1440x900 shows the whole
  workspace on one screen with Overview, Red flags and Agents tabs working; 390px stacks with no
  horizontal scroll; nav links are Analyze, Live, Cases, Campaigns, Red team; the home page no
  longer mentions connecting an inbox. One simulated signed webhook mail was used and deleted.

## 2026-10-08: Held scam mail, censored details and dissection for every inbox email

- **Found:** "only 2 emails" was AgentBoxD screening. The workspace has "Agents get only screened
  mail" on: mail its check flags (phishing 0.98 on the test scams) is `held`, `wait` never returns
  it, and reads return metadata only (subject `[held: phishing]`, no text); `/raw` answers
  `409 message_withheld`, `include_held=true` answers `403` without the `messages:release` permission
  (agentboxd.com/docs/api#screening). Also seen: `429 rate_limited` (120 req/min) because another
  backend polls the same inbox with the same key; this backend logged only the 429s.
- **Changed:** the poller asks with `include_unscreened=true` (no permission needed) so mail arrives
  before screening finishes, adds `include_held=true` when `AGENTBOXD_INCLUDE_HELD=true` (needs a key
  with `messages:release`), skips a message that still comes back `withheld` (logged, instead of
  analyzing an empty body), and on 429 waits the API's `retry_after_seconds`.
- **Changed:** `/live` shows every inbox email's subject, masked sender and a censored preview, and
  dissects every one (new `GET /inbox/live/{key}`: the case, partially censored server-side, id and
  share token null). New `services/livefeed.py`: names to initials, addresses to `sh***@domain`,
  digit runs to `***42`, long tokens to `AbCd***`; links and domains kept as evidence. First names
  inside body text are not detected. The dissection polls every 1.5s and shows the pipeline, the
  censored email and the verdict report (share mode). The page copy now says the inbox is public.
- **Verified:** pytest 93 passed (feed and detail censoring in both modes, 404s, censor rules,
  retry-after, screening opt-ins). tsc, eslint, build. `include_unscreened` accepted by AgentBoxD
  (read-only probe, HTTP 200). Private mode (`INBOX_PUBLIC` unset) with one simulated signed webhook
  (no real mail, record deleted after): the row showed subject, masked sender and preview; the panel
  streamed the pipeline, the censored email and the verdict. My backend now runs with
  `AGENTBOXD_POLL=false` so it does not compete with the other poller.

## 2026-10-08: Auto inbox checker fixed and made default; live dissection on /live

- **Fixed (real bug):** the AgentBoxD poller never ingested a message. `GET /v1/messages/{id}` returns
  the bare message, which has its own `"data": null` field; `get_message` unwrapped `data` and got
  `None`, so every poll raised `'NoneType' object has no attribute 'get'` (seen in the log every
  ~6s; a real mail at 14:17 was missed). Unwrap only a dict envelope. Regression test fails on the
  old code.
- **Fixed:** the inbox `wait` endpoint's `since` is inclusive (probed read-only: since = a message's
  `received_at` returns that message), so the poller now steps 1 ms past a message it just handled
  instead of re-fetching it in a loop.
- **Changed:** `AGENTBOXD_POLL` is now optional: unset means poll whenever AgentBoxD is configured
  and no webhook secret is set (`Settings.agentboxd_polling`). Explicit true/false still wins.
- **Added:** `/live` gains a "Live dissection" panel: follows the newest openable email (or the row
  you click; "Follow newest" returns), streams the nine agents over SSE (`PipelineView narrow`), then
  the full `VerdictReport`. The SSE + polling logic moved out of `CaseView` into
  `components/aegis/use-live-analysis.ts` (CaseView behaviour unchanged). Feed refresh is now 2s.
- **Verified:** pytest 90 passed. tsc, eslint, build. Simulated one signed webhook mail (no real
  mail, record deleted after): the panel streamed the pipeline and rendered the report; at 1440px
  the narrow pipeline shows 5 readable cards a row. Backend restarted with only the AgentBoxD values
  and `INBOX_PUBLIC=true` as process env vars: "poller started", no poll errors. A real email
  through the new poller is pending (waiting for one to be sent).

## 2026-10-08: Live test inbox page (/live)

- **Added:** `GET /api/v1/inbox/live` (`routes.py`): latest mail that reached the AgentBoxD inbox
  (sources poller/webhook, this inbox id) with per-stage progress, verdict, reply flag and an opaque
  row key. `id`, `subject` and a masked sender (`sh***@gmail.com`, never the display name) only for
  public inbox mail (`INBOX_PUBLIC=true`); private rows show progress and verdict only.
  `{"enabled": false}` without AgentBoxD. Documented in docs/API.md, typed in lib/api.ts.
- **Added:** `/live` page (`components/aegis/live-inbox.tsx`): address card with Copy and Open mail
  app, a Listening indicator, three steps, a privacy line that matches the server setting, then a
  feed polled every 3s (paused while the tab is hidden). New mail flashes and raises a toast; each
  row shows a 9-segment stage bar, the running stage, verdict, duration and "replied"; public rows
  open their case.
- **Changed:** the home hero button ("Send a random email to <address>") now links to `/live`
  instead of opening the mail app (the mailto moved onto the page).
- **Verified:** pytest 86 passed (new: private and public feed, disabled feed). tsc, eslint, build.
  Backend run with the AgentBoxD values plus `INBOX_PUBLIC=true` and a local webhook secret as process
  env vars (no `.env` written). Posted one signed fake `message.received` webhook (no real mail): the
  open /live page showed the row by itself with stage bar and verdict (SUSPICIOUS; forensic stage
  failed because no model key is set). The fake record was then deleted from the local DB. Mobile
  390px: no horizontal scroll. A real email through AgentBoxD to the page is not yet verified.

## 2026-10-08: "Send a random email to <inbox>" hero button

- **Changed:** `landing-widgets.tsx` gains `EmailTestButton`: a `mailto:` link to the AgentBoxD inbox
  (subject "Test AEGIS", body tells the visitor to paste or forward a suspicious email). Rendered in
  the home hero after "Browse recent cases" (label "Send a random email to" + the address), only when `/config/public` reports `features.inbox` and an
  `inbox_address`, so it never points at an inbox nobody reads.
- **Verified:** tsc, eslint, build. Backend started with the AgentBoxD values as process env vars (no
  `.env` written): health `agentboxd: true`, poller started, config returns
  `zesty-willow-3025@homingbox.net`. Hero screenshot shows the button; its href is the expected
  mailto. End-to-end (mail in, verdict reply out) not yet exercised.

## 2026-10-08: Campaign operator map replaces the force graph

- **Changed:** `campaigns-view.tsx`: the force-directed graph (random layout, overlapping labels) is
  replaced by a fixed three-column operator map: emails (deduped, wrap to 2 lines, open their case),
  an operator hub, and shared infrastructure grouped by type with coverage (`4/4` = in 4 of 4
  emails). SVG connectors are measured from the rendered rows; hovering or focusing a row lights
  its connectors (moving dashes, `.aegis-flow` in `globals.css`, off under reduced motion) and dims
  rows it does not touch. The separate infrastructure and linked-email lists and the "All
  campaigns" toggle are gone (the map and the campaign list cover them). Below `md` the columns
  stack without connectors. `components/aegis/force-graph.tsx` deleted.
- **Note:** `react-force-graph-2d` is no longer imported anywhere but is still in `package.json`.
- **Verified:** tsc, eslint, build. Screenshots at 1440px (apple and gmail-sender campaigns, hover
  on the sender row lights its path and dims the template) and 390px (stacked, scrollWidth 390).

## 2026-10-08: Campaigns page redesign, duplicate campaign ids, test data cleanup

- **Fixed:** duplicate React key on /campaigns. Campaign ids were `c_` + the first 8 chars of the
  earliest member id, which is a millisecond timestamp, so campaigns seeded within ~4s collided.
  Now `c_` + 10 hex of SHA-256 of the full id (`services/campaigns.py`). Regression test
  `test_campaign_ids_unique_for_close_submissions` fails on the old code, passes now (83 tests).
- **Changed:** /campaigns rebuilt (`components/aegis/campaigns-view.tsx`): stat strip, sticky campaign
  list named by operator (sender domain, else address, domain, link, phone) with verdict bar and
  indicator icons, detail pane with first/last seen, a graph focused on the selected campaign
  (zoom-to-fit, capped at 2x, "All campaigns" toggle dims the others), deduped linked emails and
  infrastructure grouped by type. New `components/aegis/force-graph.tsx` wrapper passes the graph ref
  through `next/dynamic` and sets link distance and charge range.
- **API:** campaign `analyses[]` gain `created_at`; graph nodes document the existing `campaign` field
  (docs/API.md, lib/api.ts).
- **Data:** deleted the 28 manually pasted (`source='web'`) analyses from the local
  `backend/data/aegis.db` with their stage runs and entities (user request). Backup kept outside the
  repo in the session scratchpad.
- **Also:** AgentBoxD key checked read-only: valid, inbox `zesty-willow-3025@homingbox.net` active.
  Not wired: `backend/.env` does not exist yet (user to create it).
- **Verified:** pytest 83 passed, tsc, eslint, build. Screenshots at 1440px (focus and all-campaigns
  graphs, settled) and 390px (no horizontal scroll). The browser console was not checked for the
  key warning (prod build); uniqueness is covered by the test.

## 2026-10-07: HUD corner marks follow the rounded corners

- **Changed:** `app/globals.css` `.hud::before`: the corner marks were square L-brackets (gradient
  strokes) and clashed with the rounded panel corners. They are now a 1px rounded ring 8px inside
  the border with radius `--hud-r - 8px` (concentric), masked to 20px at each corner. `.hud`
  takes its radius from `--hud-r`; the two 24px panels (home red-team panel, verdict report) use
  `[--hud-r:1.5rem]` instead of `rounded-3xl` / `rounded-[1.5rem]`.
- **Verified:** build; computed panel radius 24px and mark radius 16px on the red-team panel,
  `mask-composite: intersect` applied; home screenshot shows curved marks on every panel corner.
  Hover (`.hud-interactive`) recolors through `--m` (by code, not checked in browser).

## 2026-10-07: Background still choppy, follow-up

- **Changed:** `liquid-metal.tsx`: 30 fps cap removed (draws every display frame again); new
  `intensity` prop mixes the chrome toward `#0a0c0e` in the shader. `AppBackground` passes
  `intensity={0.45}` instead of the CSS `opacity-45` class.
- **Why:** The cap made the flow step every 2nd frame at 60 Hz and unevenly (4 or 5 frames) at
  144 Hz, which reads as stutter; the half-res shader costs ~0.6 ms so it can run every frame.
  CSS opacity added a full-screen layer blend per frame.
- **Verified:** tsc, eslint, build. No long tasks on / or /analyze during a scroll. Canvas
  720x450, wrapper opacity 1, screenshot matches the previous look. Smoothness on a real display
  not measured.

## 2026-10-07: Background performance (lag and low fps)

- **Changed:** `.hud` lost `backdrop-filter: blur(6px)` (`app/globals.css`); site nav lost
  `backdrop-blur-xl`, fill raised from 0.78 to 0.92. `liquid-metal.tsx` renders at half CSS
  resolution (`RENDER_SCALE`) and caps drawing at 30 fps (`FRAME_MS`).
- **Why:** With an animated background every backdrop-filter region (35 `.hud` uses plus the
  nav) is re-blurred every frame; with the old static dots it was blurred once. Panels are 82%
  opaque, so the blur was barely visible.
- **Verified:** tsc, eslint, build. Shader benchmark in headless Chrome, 20 draws each: 1.1 ms
  at 1440x900, 0.6 ms at 720x450 (so the shader alone was not the main cost here). On /analyze:
  canvas 720x450 for a 1440x900 viewport, zero elements with a backdrop filter, screenshot
  unchanged in look. Real-GPU frame rate not measured; headless rAF is not display-bound.

## 2026-10-07: Liquid metal background replaces the animated gradient

- **Changed:** new `frontend/components/ui/liquid-metal.tsx`, a port of the educalvolpz
  "liquid-metal" WebGL2 shader from 21st.dev, chrome palette only, pointer input removed (no
  listeners, no `uPointer`). `AppBackground` renders it at 45% opacity under the vignette.
  `components/ui/animated-gradient.tsx` deleted (no other users). `brand.md` updated.
- **Why:** User asked for this background across the site, not reacting to the mouse.
- **Verified:** `tsc --noEmit`, eslint, `npm run build`. WebGL2 canvas at 1440x900; two
  screenshots 2s apart differ (animating). Screenshots of / and /analyze: copy and panels
  readable. 25% opacity was tried first and the chrome texture was barely visible.

## 2026-10-07: Animated gradient background

- **Changed:** new `frontend/components/ui/animated-gradient.tsx`, a port of the componentry
  "animated-gradient" WebGL2 shader from 21st.dev (Edge shape, Aurora preset parameters, AEGIS
  colors `#0a0c0e` / `#121a08` / `#d9ff3d`). `AppBackground` renders it at 25% opacity under the
  existing vignette, replacing the dot pattern. `brand.md` updated (it still named `SonarGrid`).
- **Why:** User asked for that background, whole site, brand lime, toned down.
- **Notes:** Renders at 1x pixel ratio to keep the full-screen shader cheap. Reduced motion draws
  one still frame; no WebGL2 leaves the plain page background.
- **Verified:** `tsc --noEmit`, eslint, `npm run build`. Canvas present with a WebGL2 context at
  1440x900. Screenshots of /, /analyze (1440px) and / (390px): hero copy and panels readable.
  40% opacity was tried first and washed out the hero body text.

## 2026-10-07: Border beam turns corners smoothly

- **Changed:** `frontend/components/ui/border-beam.tsx` rewritten. The streak is now six stacked
  dashes on an SVG rounded-rect stroke (sized by `ResizeObserver`), driven by one `motion` value,
  instead of a 90px square riding `offset-path` with auto-rotate under a ring mask. Props unchanged.
- **Why:** At each rounded corner the square spun 90 degrees over a ~30px arc, so the masked slice
  jumped (visible jitter). A dash follows the curve exactly with no rotation.
- **Verified:** `tsc --noEmit`, eslint, `npm run build`. On /analyze, sampled the head dash offset
  over 120 frames: monotonic, no stalled frames. Screenshot caught the streak mid-corner, following
  the curve. Applies to all three users (analyze form, red team, verdict report).
- **Follow-up:** the streak restarted at the top-left corner (the path start) because the dash
  pattern period was dash + perimeter, so the tail could not wrap. Gap is now perimeter - dash.
  Verified by freezing a dash 30px past the start: one unbroken streak from the left edge, round
  the corner, onto the top edge.

## 2026-10-07: Analyze form border beam stays on the panel

- **Changed:** `frontend/components/aegis/analyze-form.tsx`, `self-start` on the form's `BorderBeam`.
- **Why:** As a grid item the beam wrapper stretched to the taller samples column, so the streak
  traced an invisible box below the form panel.
- **Verified:** `npm run build`; at 1440px the wrapper and form bounds now match (277 to 773 px,
  row 277 to 953) and a screenshot shows the streak on the panel edge.

## 2026-10-07: Docs for Google + Microsoft sign-in

- **Changed:** README (features, privacy bullets, env table with `MICROSOFT_*`, Microsoft setup
  steps, limits), ARCHITECTURE (providers, mailboxes and sign-in sections), docs/API.md (generic
  `/oauth/{provider}/*` routes, `/oauth/status`, `/oauth/pairing`, `/oauth/confirm`, Mailbox shape
  with `manage_url`, `POST /mailboxes` removed), DECISIONS D11, privacy page delete wording,
  CLAUDE.md test count (84 to 82).
- **Why:** The docs still described IMAP and app passwords and Google-only route names after
  commit `894acab`.
- **Verified:** Every route, status, scope, label mode and error path in the docs checked against
  `api/routes.py`, `services/mailboxes.py` and `providers/{oauth,google,microsoft}.py`. 82 backend
  tests pass. No code changed apart from one sentence of UI copy.

## 2026-10-06: Sign in with Microsoft, IMAP removed

- **Changed:** `providers/oauth.py` (shared PKCE flow), `providers/microsoft.py` (Graph: new mail by
  received time, categories + flag), generic `/oauth/{provider}/*` routes and `/connect?state=`;
  `providers/imap.py` and `POST /mailboxes` deleted; DotPattern site background. See D11.
- **Why:** Google and Microsoft cover most users with no passwords; Yahoo and iCloud have no usable
  mail sign-in for apps.
- **Verified:** 82 backend tests (7 in `test_oauth.py` with fake Google and Graph); mutation check
  18/18 caught.
- **Not verified:** Microsoft flow in a browser, the dot background in a browser, any real account.

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
