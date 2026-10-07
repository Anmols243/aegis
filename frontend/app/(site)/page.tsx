import Link from "next/link"
import { ArrowRight, Eye, FileSearch, Fingerprint, Gavel, Globe, Mail, Network, ScanText, ShieldCheck, Sparkles } from "lucide-react"

import { InboxCallout, LiveCounters } from "@/components/aegis/landing-widgets"
import { PrivacyPromises } from "@/components/aegis/privacy-promises"
import { BorderBeam } from "@/components/ui/border-beam"

const PIPELINE = [
  { name: "parse", icon: ScanText, text: "Reads the raw email or .eml file: headers, body, links, attachments." },
  { name: "triage", icon: Sparkles, text: "A fast model extracts every sender, link, phone number and brand. Extraction only, no judgement." },
  { name: "signals", icon: Fingerprint, text: "15 deterministic checks: SPF, DKIM, DMARC, lookalike domains, homoglyphs, hidden links, gift-card and executive impersonation. Facts, not guesses." },
  { name: "forensic", icon: FileSearch, text: "A long-context analyst writes findings. Each one must quote the email, or it is thrown away." },
  { name: "vision", icon: Eye, text: "Renders the email offline and asks a vision model whether it imitates a real brand's login page." },
  { name: "sandbox", icon: Globe, text: "Fetches each link with no JavaScript and strict network guards, looking for password forms and downloads." },
  { name: "graph", icon: Network, text: "Links this email to earlier ones that share domains, senders, phones or templates: campaigns." },
  { name: "arbiter", icon: Gavel, text: "Weighs every signal, requires independent agreement for a SCAM call, and fails closed when unsure." },
  { name: "report", icon: ShieldCheck, text: "A plain-language verdict with what to do next, the evidence, and a link you can share." },
]

export default function LandingPage() {
  return (
    <div>
      <section className="relative mx-auto flex max-w-5xl flex-col items-center px-4 pb-14 pt-20 text-center sm:px-6 sm:pt-28">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_40%_42%_at_50%_42%,rgba(10,12,14,0.95)_0%,transparent_100%)]"
        />
        <p className="mb-6 inline-flex items-center gap-2 rounded-full border border-hair bg-surface/80 px-3.5 py-1.5 font-mono text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
          <span className="size-1.5 rounded-full bg-lime shadow-[0_0_10px_var(--aegis-lime)] [animation:aegis-pulse_2s_infinite]" aria-hidden="true" />
          Multi-agent scam defense
        </p>
        <h1 className="font-display text-balance text-5xl font-extrabold leading-[1.02] tracking-tight text-ink sm:text-6xl md:text-7xl">
          Spot the scam.
          <br />
          <span className="text-lime">See the evidence.</span>
        </h1>
        <p className="mt-6 max-w-2xl text-pretty text-base text-muted-foreground sm:text-lg">
          Paste a suspicious email. A team of AI agents takes it apart and tells you, in plain language, whether it is a scam and exactly why, quoting
          the lines that give it away.
        </p>
        <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/analyze"
            className="group inline-flex h-12 items-center gap-2 rounded-full bg-lime px-7 text-sm font-semibold text-black shadow-[0_0_24px_rgba(217,255,61,0.35)] transition-transform active:scale-[0.98]"
          >
            Analyze an email
            <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
          </Link>
          <Link
            href="/cases"
            className="inline-flex h-12 items-center rounded-full border border-hair bg-surface/80 px-7 text-sm font-medium text-ink backdrop-blur transition-colors hover:border-lime/40"
          >
            Browse recent cases
          </Link>
        </div>
        <div className="mt-6">
          <InboxCallout />
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
        <LiveCounters />
      </section>

      <section className="mx-auto max-w-7xl px-4 pb-20 sm:px-6">
        <div className="mb-8 max-w-2xl">
          <p className="label-mono mb-3 text-lime">How it works</p>
          <h2 className="font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">Nine specialists, one verdict you can check.</h2>
          <p className="mt-3 text-muted-foreground">
            Spam filters give you a silent yes or no. AEGIS shows its work: every claim in the verdict points at the line, link or header it came from.
          </p>
        </div>
        <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {PIPELINE.map((s, i) => (
            <li key={s.name} className="hud hud-interactive p-5">
              <div className="mb-3 flex items-center gap-3">
                <span className="flex size-9 items-center justify-center rounded-lg border border-lime/25 bg-lime/5 text-lime">
                  <s.icon className="size-4" aria-hidden="true" />
                </span>
                <span className="font-mono text-[11px] text-faint">{String(i + 1).padStart(2, "0")}</span>
                <span className="font-mono text-sm font-semibold uppercase tracking-[0.14em] text-ink">{s.name}</span>
              </div>
              <p className="text-sm leading-relaxed text-muted-foreground">{s.text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="inbox-heading" className="mx-auto max-w-7xl px-4 pb-20 sm:px-6">
        <div className="hud p-6 sm:p-9">
          <div className="mb-7 grid gap-6 md:grid-cols-[1.3fr_auto] md:items-end">
            <div className="max-w-2xl">
              <p className="label-mono mb-3 text-lime">New: connect your inbox</p>
              <h2 id="inbox-heading" className="font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">
                It watches your inbox. It never takes over.
              </h2>
              <p className="mt-3 text-muted-foreground">
                Sign in with Google or Microsoft and every new email is checked in the background and scams get an
                AEGIS label, with the full evidence one click away. Privacy is the design, not a setting:
              </p>
            </div>
            <Link
              href="/inbox"
              className="group inline-flex h-12 items-center gap-2 justify-self-start rounded-full bg-lime px-7 text-sm font-semibold text-black shadow-[0_0_24px_rgba(217,255,61,0.35)] transition-transform active:scale-[0.98] md:justify-self-end"
            >
              <Mail className="size-4" aria-hidden="true" />
              Connect your inbox
              <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
            </Link>
          </div>
          <PrivacyPromises compact />
          <p className="mt-5 text-xs text-faint">
            Details on the{" "}
            <Link href="/privacy" className="text-lime underline-offset-4 hover:underline">
              privacy page
            </Link>
            .
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-4 pb-24 sm:px-6">
        <BorderBeam className="rounded-3xl" radius={24} duration={9}>
          <div className="hud grid gap-6 p-7 [--hud-r:1.5rem] sm:p-9 md:grid-cols-[1.2fr_1fr] md:items-center">
            <div>
              <p className="label-mono mb-3 text-lime">Built to be attacked</p>
              <h2 className="font-display text-2xl font-bold tracking-tight text-ink sm:text-3xl">A red team that never sleeps.</h2>
              <p className="mt-3 text-muted-foreground">
                A mutation engine rewrites real scams with homoglyphs, fresh lookalike domains, hidden links and prompt-injection payloads, then fires
                them at the pipeline. Every miss is kept and replayed until it is caught.
              </p>
              <Link href="/redteam" className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-lime underline-offset-4 hover:underline">
                Open the red-team arena <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            </div>
            <div className="flex flex-col gap-3">
              <p className="label-mono">Powered by</p>
              <div className="flex flex-wrap gap-2">
                {["Featherless AI", "AgentBoxD", "Kimi K3", "Qwen3 VL", "FastAPI", "Next.js"].map((t) => (
                  <span key={t} className="rounded-full border border-hair bg-surface px-3 py-1.5 font-mono text-[11px] uppercase tracking-[0.1em] text-ink/85">
                    {t}
                  </span>
                ))}
              </div>
              <p className="text-xs text-faint">
                Models run on Featherless. The inbox, inbound phishing scores and prompt-injection labels come from AgentBoxD.
              </p>
            </div>
          </div>
        </BorderBeam>
      </section>
    </div>
  )
}
