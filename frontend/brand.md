# AEGIS brand and design tokens

Dark radar / HUD look: near-black surfaces, hairline borders, one lime accent,
mono uppercase labels, verdict colors used only for verdicts.

## Color

| Token (CSS var) | Value | Use |
|---|---|---|
| `--aegis-bg` | `#0A0C0E` | page background |
| `--aegis-bg-deep` | `#000000` | deepest wells |
| `--aegis-surface` | `#121518` | panels |
| `--aegis-surface-2` | `#171B20` | popovers, raised surfaces |
| `--aegis-ink` | `#EDEDE8` | primary text |
| `--aegis-muted` | `#8A8F98` | secondary text, labels |
| `--aegis-faint` | `#5A6068` | tertiary text, hints |
| `--aegis-hair` | `rgba(255,255,255,.08)` | hairline borders |
| `--aegis-lime` | `#D9FF3D` | the accent: CTAs, active state, focus ring, sonar dots |
| `--aegis-scam` | `#FF5C5C` | SCAM verdicts, high severity |
| `--aegis-susp` | `#FFB224` | SUSPICIOUS verdicts, medium severity |
| `--aegis-safe` | `#3DDC97` | LIKELY SAFE verdicts |

shadcn semantic tokens (`--primary`, `--background`, `--border`, ...) are mapped
onto these in `app/globals.css`; `--primary` is lime, so `text-primary` (used by
the sonar grid) is lime. Tailwind color utilities: `lime`, `scam`, `susp`,
`safe`, `ink`, `faint`, `surface`, `surface-2`, `hair`.

## Type

- Display: Montserrat 600 to 800 (`font-display`), headlines and the wordmark.
- Body: Inter (`font-sans`).
- Mono: JetBrains Mono (`font-mono`), labels, scores, ids, evidence.
- Micro-label: `.label-mono` (10.5px, uppercase, 0.18em tracking, muted).

## Components

- `.hud`: panel with dark translucent fill, hairline border, 20px radius and
  lime viewfinder marks in each corner. Add `.hud-interactive` to brighten the
  marks and border on hover.
- `.chip`: filter pill, dark fill with a lime outline; `data-active="true"` is
  solid lime with black text.
- `.evidence-mark`: inline highlight of quoted evidence in an email
  (`data-sev="high|medium|low"`).
- `LiquidMetal` (`components/ui/liquid-metal.tsx`): WebGL2 liquid-chrome
  surface, used by `AppBackground` as the app-wide fixed background at 45%
  opacity under a vignette. Ignores the pointer. Still frame under reduced motion.
- `BorderBeam` (`components/ui/border-beam.tsx`): lime streak orbiting the border
  of key panels at constant speed.
- `DotPattern` (`components/ui/dot-pattern.tsx`): faded dot grid behind
  scrollable content, pinned outside the scroller.

## Rules

- Lime is the only accent. Verdict colors appear only on verdicts and severities.
- Motion respects `prefers-reduced-motion` (beams hidden, background still, transitions off).
- Focus is always visible: 2px lime outline.
- No em or en dashes in copy.
