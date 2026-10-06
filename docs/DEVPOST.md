# Devpost write-up (draft)

**Track:** AI + Cybersecurity

## Inspiration
Phishing is still the most common way people get compromised, and generative AI has made lures
fluent, personalised and visually convincing. Spam filters give a silent verdict, so people never
learn why a message was a scam. We wanted a tool that shows its work, the way a security analyst would.

## What it does
Paste an email, drop an `.eml` file, or forward it to the AEGIS inbox. Nine specialist agents
analyse it in about 15 seconds and return SCAM, SUSPICIOUS or LIKELY SAFE, with every red flag
quoting the exact line, link or header it came from, plain-language next steps tailored to the scam,
and a share link for family members. Related scams are clustered into campaigns, and a red-team
arena attacks the pipeline with mutated scams to show what it still catches.

## How we built it
- **Backend:** FastAPI (async), SQLite as store and job queue, a dependency-graph pipeline whose
  progress streams to the browser over server-sent events.
- **AI:** Featherless-hosted open models. Kimi K3 for extraction and forensic analysis, Qwen3-VL for
  visual brand-impersonation checks on a sandboxed render.
- **Deterministic layer:** 15 checks (SPF/DKIM/DMARC, lookalike and homoglyph domains, hidden links,
  sender spoofing, gift-card and executive impersonation) that the AI reasons over as verified facts.
- **Arbiter:** weighted ensemble with a corroboration rule (two independent strong sources for SCAM)
  and fail-closed behaviour.
- **AgentBoxD:** the inbox, its inbound phishing and prompt-injection scores, and in-thread replies.
- **Frontend:** Next.js, TypeScript, Tailwind and shadcn/ui.

## Challenges
- Keeping an LLM honest: every finding's quote is verified against the email in code; fabricated
  evidence is dropped.
- Fetching attacker links safely: the sandbox pins connections to vetted public IPs and re-checks
  every redirect hop, closing DNS rebinding and redirect-to-internal tricks.
- Scams with no links (CEO gift-card fraud) needed deterministic language checks, not link scanning.

## Accomplishments
- 22 of 22 emails correct on our evaluation set with real models, zero false positives
  (small synthetic set; a sanity check, not a real-world accuracy claim).
- A phish that tells the AI to "classify this as safe" is still flagged, and the attempt is
  reported as a red flag.
- 78 automated tests, including SSRF tests against a real local server.

## What we learned
Grounding beats prompting: asking a model to cite evidence is not enough, checking the citation is.

## What works and what does not
See the README section of the same name. Not yet verified in v2: the live AgentBoxD webhook and
auto-reply (tested with signed fixtures), and the Docker image build.

## What's next
Attachment content analysis, JavaScript-capable sandboxing in an isolated VM, a browser extension
for one-click checks, and Postgres + Redis for multi-instance deployment.

## Built with
python, fastapi, sqlalchemy, sqlite, playwright, featherless-ai, kimi-k3, qwen3-vl, agentboxd,
next.js, react, typescript, tailwindcss, shadcn-ui
