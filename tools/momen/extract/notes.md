# Momen AEGIS dashboard — extraction notes for the standalone copy

Source: Momen project `l7YRy8q8DR7`, web app `8bD5JlV4jnX`, page `tqvfjce6e` ("Page 1").
Full tree: `tree.json` (159 components). Raw parsed infos: `info_parsed.json`.

## Page model — ONE long scrolling page, not separate views

Navigation is `scroll-page-to` on button click (no routing, no view switching):
- Feed nav → scrolls to `q6im9nx91` (feed/mail section)
- Campaign nav → scrolls to `rj6gzghgk` ("Campaigns View")
- Red team nav → scrolls to `cilx069jq` ("Red Team View")
- "Campaign Link Button" in reader → scrolls to campaigns view
- The rail contains TWO sets of nav buttons: first set (F/C/R, no events),
  second set (with onClick). Likely desktop vs phone variants — the copy uses
  one set with smooth-scroll behavior.

## Layout skeleton

- Page: flex row, justify center, align flex-start.
- **Floating rail** (`r9udyc4m6`): fixed, left 20, top 112, width 84, z 30,
  column, gap 10, align center, padding 12/8, radius 20,
  bg rgba(18,21,24,0.82), border 1px rgba(255,255,255,0.12).
  Children: "A." wordmark, F / C / R nav buttons (48×44, radius 14).
  Active nav btn: bg #FFFFFF18, border #FFFFFF40, shadow 0 2 12 rgba(0,0,0,.25).
  Inactive: bg #FFFFFF08, border #FFFFFF1A, text #8A8F98, D-DIN-PRO 600.
- **Content column** (`b07h0ngpg`): column, gap 28, align flex-start.
  Order: Top Bar → Try It Live Strip → Stat Strip → Feed Controls →
  Mail Workspace → Campaigns View → Red Team View.

## Typography (exact)

- Headings/wordmarks: **Montserrat** (AEGIS. 28px; section titles 26px;
  subject 24px; rail "A." 18px 700).
- Data/mono: **D-DIN-PRO** (stamps 10px 700; stat values 30px; meta 10-11px;
  labels 9-10px uppercase-ish; scores).
- Body: **Inter** (steps 13px; explanations 13px; flags 12px; actions 12px).
- Colors: ink #EDEDE8, muted #8A8F98, surface #121518, page bg #0A0C0E,
  hairline rgba(255,255,255,0.08–0.12).
- Verdict semantics: SCAM #FF5C5C / SUSPICIOUS #FFB224 / LIKELY_SAFE #3DDC97.

## Verdict stamp recipe (glass pill)

- SCAM: bg rgba(255,92,92,.12), text #FF5C5C, border rgba(255,92,92,.34)
- LIKELY_SAFE: bg rgba(61,220,151,.10), text #3DDC97, border rgba(61,220,151,.32)
- SUSPICIOUS (inferred same pattern): bg rgba(255,178,36,.12), text #FFB224,
  border rgba(255,178,36,.34)
- 10px D-DIN-PRO 700, radius 16, padding 6/11, letterSpacing .7, lineHeight 14.

## Filter chips

- Active: bg #FFFFFF18, border #FFFFFF40, text #EDEDE8, Inter 600 12px,
  radius 16, padding 8/14.
- Inactive: bg #FFFFFF08, border #FFFFFF1A, text #8A8F98, D-DIN-PRO 600 11px.

## Mail list rows — NOT extractable (inside CONDITIONAL_VIEW branches)

`wm15bcf6p` "Scam Search Gate" and `bnwvfr4q6` "Safe Search Gate"
(properties only `{preserveStateOnSwitch: true}`) each wrap one verdict row
and show/hide it by filter+search state. Branch contents are not exposed by
any read op. The copy implements rows natively in JS in the established
language: stamp pill + subject (Inter) / sender · time (D-DIN-PRO muted) +
score (D-DIN-PRO, verdict-colored). Selected row gets the lime edge.

## Data — static seed baked in, NO live queries

The Momen app has no API/data queries; every value is a literal. Seed:
- Verdict 1: live-demo-phish-001, SCAM, 0.748, conf 41% "Low", Disagreed,
  19.5s, 2 flags; sender security@paypa1-secure.com;
  subject "We detected unusual activity on your PayPal account".
- Verdict 2: live-test-newsletter-001, LIKELY_SAFE, 0.137, conf 76% "High",
  sender [email] (redacted); subject "PyWeekly #812".
- Top bar shows "LAST REFRESH · CACHED SEED" and an "OFFLINE — CACHED" badge;
  motion badge reads "MOTION · STILL".
- Try-it-live strip: 3 steps + "FORWARDING ADDRESS NOT PROVIDED · copy action
  disabled" notice (the user later supplied zesty-willow-3025@homingbox.net).
- Campaigns: 1 card, 17 emails · 1 scam; infra chips DOMAIN paypa1-secure.com,
  DOMAIN paypa1-secure.xyz, URL "2 linked", "+4 technical fingerprints".
- Red team: 5/0/5/0/5; honesty note; axis breakdown; 3 case rows shown
  (rt-20261004-001/002/003) with "FLAGGED · SUSPICIOUS" stamps.

The standalone copy replaces all of this with the LIVE API (see task) and
keeps the seed only as the offline fallback.
