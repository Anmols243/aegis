"use client"

import * as React from "react"
import Image from "next/image"
import Link from "next/link"
import { CheckCircle2, Copy, ExternalLink, FileWarning, Link2, Loader2, Share2 } from "lucide-react"
import { toast } from "sonner"

import { ScoreGauge, SectionTitle, SeverityPill, VerdictBadge } from "@/components/aegis/bits"
import { BorderBeam } from "@/components/ui/border-beam"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { DotPattern } from "@/components/ui/dot-pattern"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { api, type Analysis, type SandboxResult } from "@/lib/api"
import { LABEL_META, pct, prettyKey, seconds } from "@/lib/format"
import { highlightSegments, topSeverity, type HighlightNote } from "@/lib/highlight"
import { cn } from "@/lib/utils"

export function VerdictReport({ analysis, mode = "full" }: { analysis: Analysis; mode?: "full" | "share" }) {
  const a = analysis
  const v = a.verdict
  const label = v?.label ?? a.label
  const meta = label ? LABEL_META[label] : null

  return (
    <div className="flex flex-col gap-6">
      <BorderBeam className="rounded-[1.5rem]" radius={24} duration={9} colorFrom={meta ? meta.color : "#d9ff3d"}>
        <section className="hud grid gap-6 rounded-[1.5rem] p-5 sm:p-7 md:grid-cols-[auto_1fr] md:items-center" aria-label="Verdict">
          <div className="flex justify-center">
            <ScoreGauge score={v?.score ?? a.score} label={label} />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-3">
              <VerdictBadge label={label} size="lg" />
              {v ? (
                <span className="font-mono text-xs text-muted-foreground">
                  confidence {pct(v.confidence)} · agreement {v.agreement} · evidence {pct(v.evidence_completeness)}
                </span>
              ) : null}
            </div>
            <p className={cn("mt-3 font-display text-2xl font-bold leading-tight tracking-tight sm:text-3xl", meta?.tw ?? "text-ink")}>
              {meta?.plain ?? "Verdict pending."}
            </p>
            {a.summary ? <p className="mt-3 max-w-3xl text-pretty text-muted-foreground">{a.summary}</p> : null}
            {v?.corroboration?.length ? (
              <ul className="mt-4 flex flex-wrap gap-2" aria-label="Independent sources that agree">
                {v.corroboration.map((c) => (
                  <li key={c} className="inline-flex items-center gap-1.5 rounded-full border border-hair bg-black/30 px-3 py-1 text-xs text-ink/85">
                    <CheckCircle2 className="size-3.5 text-lime" aria-hidden="true" />
                    {c}
                  </li>
                ))}
              </ul>
            ) : null}
            {mode === "full" ? (
              <div className="mt-5 flex flex-wrap gap-2">
                <ShareButton token={a.share_token} />
                <AbuseReportButton id={a.id} />
              </div>
            ) : null}
          </div>
        </section>
      </BorderBeam>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="flex min-w-0 flex-col gap-6">
          {a.actions?.length ? (
            <section className="hud p-5 sm:p-6" aria-labelledby="actions-title">
              <SectionTitle>
                <span id="actions-title">What to do next</span>
              </SectionTitle>
              <ol className="flex flex-col gap-2.5">
                {a.actions.map((step, i) => (
                  <li key={i} className="flex gap-3 text-[15px] leading-relaxed text-ink">
                    <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-lime font-mono text-[11px] font-bold text-black">
                      {i + 1}
                    </span>
                    {step}
                  </li>
                ))}
              </ol>
            </section>
          ) : null}

          {a.red_flags?.length ? (
            <section className="hud p-5 sm:p-6" aria-labelledby="flags-title">
              <SectionTitle aside={<span className="font-mono text-xs text-faint">{a.red_flags.length}</span>}>
                <span id="flags-title">Red flags</span>
              </SectionTitle>
              <ul className="flex flex-col divide-y divide-hair">
                {a.red_flags.map((f, i) => (
                  <li key={i} className="flex flex-col gap-1.5 py-3 first:pt-0 last:pb-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <SeverityPill severity={f.severity} />
                      <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-faint">{f.source}</span>
                    </div>
                    <p className="text-[15px] font-medium text-ink">{f.title}</p>
                    {f.evidence ? <q className="break-words font-mono text-[12.5px] text-muted-foreground">{f.evidence}</q> : null}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {mode === "full" && a.email ? <EmailEvidence analysis={a} /> : null}

          {a.signals?.length ? (
            <section className="hud p-5 sm:p-6" aria-labelledby="signals-title">
              <SectionTitle aside={<span className="text-xs text-faint">pure code, no AI</span>}>
                <span id="signals-title">Deterministic signals</span>
              </SectionTitle>
              <ul className="grid gap-2 sm:grid-cols-2">
                {a.signals.map((s, i) => (
                  <li key={`${s.name}-${i}`} className="flex min-w-0 flex-col gap-1 rounded-xl border border-hair bg-black/25 p-3">
                    <div className="flex items-center gap-2">
                      <SeverityPill severity={s.severity} />
                      <span className="truncate font-mono text-[11px] text-ink/80">{s.name}</span>
                    </div>
                    <p className="text-sm text-ink/90">{s.detail}</p>
                    {s.evidence ? <p className="break-words font-mono text-[11.5px] text-faint">{s.evidence}</p> : null}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {a.sandbox?.length ? <SandboxSection results={a.sandbox} /> : null}
        </div>

        <div className="flex min-w-0 flex-col gap-6">
          {a.vision ? (
            <section className="hud p-5 sm:p-6" aria-labelledby="vision-title">
              <SectionTitle>
                <span id="vision-title">Vision inspector</span>
              </SectionTitle>
              <p className="text-[15px] text-ink">
                {a.vision.impersonated_brand ? (
                  <>
                    Looks like <span className="font-semibold text-scam">{a.vision.impersonated_brand}</span> ({pct(a.vision.confidence)} confidence)
                  </>
                ) : (
                  "No brand impersonation detected in the rendered email."
                )}
              </p>
              {a.vision.reason ? <p className="mt-1.5 text-sm text-muted-foreground">{a.vision.reason}</p> : null}
              {a.vision.notable_regions?.length ? (
                <ul className="mt-2 flex flex-wrap gap-1.5">
                  {a.vision.notable_regions.map((r) => (
                    <li key={r} className="rounded-full border border-hair px-2.5 py-0.5 text-xs text-muted-foreground">
                      {r}
                    </li>
                  ))}
                </ul>
              ) : null}
              {mode === "full" && a.vision.screenshot_url ? (
                <a href={a.vision.screenshot_url} target="_blank" rel="noreferrer" className="mt-4 block overflow-hidden rounded-xl border border-hair">
                  <Image
                    src={a.vision.screenshot_url}
                    alt="Offline render of the email used by the vision inspector"
                    width={1280}
                    height={900}
                    unoptimized
                    className="h-auto max-h-80 w-full object-cover object-top"
                  />
                </a>
              ) : null}
            </section>
          ) : null}

          {a.campaign && (a.campaign.related?.length || a.campaign.note) ? (
            <section className="hud p-5 sm:p-6" aria-labelledby="campaign-title">
              <SectionTitle aside={a.campaign.campaign_id ? <span className="font-mono text-xs text-lime">{a.campaign.campaign_id}</span> : null}>
                <span id="campaign-title">Campaign links</span>
              </SectionTitle>
              {a.campaign.note ? <p className="text-sm text-muted-foreground">{a.campaign.note}</p> : null}
              {a.campaign.related?.length ? (
                <ul className="mt-3 flex flex-col gap-2">
                  {a.campaign.related.map((r) => (
                    <li key={r.analysis_id} className="rounded-xl border border-hair bg-black/25 p-3">
                      <div className="flex items-center gap-2">
                        <VerdictBadge label={r.label} />
                        <span
                          className={cn(
                            "font-mono text-[10px] uppercase tracking-[0.14em]",
                            r.strength === "high" ? "text-scam" : r.strength === "medium" ? "text-susp" : "text-faint",
                          )}
                        >
                          {r.strength} tie
                        </span>
                      </div>
                      {mode === "full" ? (
                        <Link href={`/cases/${encodeURIComponent(r.analysis_id)}`} className="mt-1.5 block truncate text-sm font-medium text-ink hover:text-lime">
                          {r.subject || r.analysis_id}
                        </Link>
                      ) : (
                        <p className="mt-1.5 truncate text-sm font-medium text-ink">{r.subject || "Related message"}</p>
                      )}
                      <p className="text-xs text-muted-foreground">{r.why}</p>
                    </li>
                  ))}
                </ul>
              ) : null}
            </section>
          ) : null}

          {v && Object.keys(v.contributions || {}).length ? (
            <section className="hud p-5 sm:p-6" aria-labelledby="weights-title">
              <SectionTitle>
                <span id="weights-title">Who decided</span>
              </SectionTitle>
              <ul className="flex flex-col gap-2.5">
                {Object.entries(v.contributions)
                  .sort((x, y) => y[1] - x[1])
                  .map(([k, val]) => (
                    <li key={k} className="flex flex-col gap-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className={cn("font-mono uppercase tracking-[0.1em]", v.strongest?.includes(k) ? "text-lime" : "text-muted-foreground")}>
                          {prettyKey(k)}
                        </span>
                        <span className="font-mono tabular-nums text-ink/80">{val.toFixed(2)}</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                        <div className="h-full rounded-full bg-lime" style={{ width: `${Math.min(100, Math.max(2, val * 100))}%` }} />
                      </div>
                    </li>
                  ))}
              </ul>
              {v.dissent?.length ? (
                <ul className="mt-4 flex flex-col gap-1.5 border-t border-hair pt-3">
                  {v.dissent.map((d) => (
                    <li key={d} className="text-xs text-susp">
                      {d}
                    </li>
                  ))}
                </ul>
              ) : null}
            </section>
          ) : null}

          {a.techniques?.length ? (
            <section className="hud p-5 sm:p-6" aria-labelledby="tech-title">
              <SectionTitle>
                <span id="tech-title">Deception techniques</span>
              </SectionTitle>
              <ul className="flex flex-wrap gap-2">
                {a.techniques.map((t) => (
                  <li key={t} className="rounded-full border border-scam/30 bg-scam/5 px-3 py-1 font-mono text-[11px] text-scam">
                    {t}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {mode === "full" && a.stages?.length ? (
            <section className="hud p-5 sm:p-6" aria-labelledby="timing-title">
              <SectionTitle aside={a.duration_s != null ? <span className="font-mono text-xs text-ink/80">{seconds(a.duration_s)} total</span> : null}>
                <span id="timing-title">Stage timings</span>
              </SectionTitle>
              <ul className="flex flex-col gap-1.5">
                {a.stages.map((s) => (
                  <li key={s.name} className="flex items-center justify-between gap-3 text-xs">
                    <span className="font-mono uppercase tracking-[0.1em] text-muted-foreground">{s.name}</span>
                    <span className={cn("font-mono tabular-nums", s.status === "failed" ? "text-scam" : s.status === "skipped" ? "text-faint" : "text-ink/85")}>
                      {s.status === "done" ? seconds(s.duration_s) : s.status}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      </div>
    </div>
  )
}

function EmailEvidence({ analysis }: { analysis: Analysis }) {
  const e = analysis.email
  const body = e.text ?? ""
  const items = React.useMemo(() => {
    const list: { excerpt: string; note: HighlightNote }[] = []
    for (const f of analysis.findings ?? []) list.push({ excerpt: f.excerpt, note: { claim: f.claim, severity: f.severity, source: "forensic" } })
    for (const s of analysis.signals ?? []) {
      if (s.evidence && s.severity !== "info") list.push({ excerpt: s.evidence, note: { claim: s.detail, severity: s.severity, source: `signal: ${s.name}` } })
    }
    for (const f of analysis.red_flags ?? []) {
      if (f.evidence) list.push({ excerpt: f.evidence, note: { claim: f.title, severity: f.severity, source: f.source } })
    }
    return list
  }, [analysis])
  const segments = React.useMemo(() => highlightSegments(body, items), [body, items])
  const marked = segments.filter((s) => s.notes.length).length

  return (
    <section className="hud overflow-hidden" aria-labelledby="email-title">
      <div className="px-5 pt-5 sm:px-6 sm:pt-6">
        <SectionTitle aside={<span className="font-mono text-xs text-faint">{marked} highlighted</span>}>
          <span id="email-title">The email, with evidence</span>
        </SectionTitle>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
          {[
            ["From", e.from],
            ["Reply-To", e.reply_to],
            ["To", e.to],
            ["Date", e.date],
            ["Subject", e.subject],
          ]
            .filter(([, val]) => val)
            .map(([k, val]) => (
              <React.Fragment key={k}>
                <dt className="font-mono text-xs uppercase tracking-[0.1em] text-faint">{k}</dt>
                <dd className="min-w-0 break-words text-ink/90">{val}</dd>
              </React.Fragment>
            ))}
          {e.attachments?.length ? (
            <>
              <dt className="font-mono text-xs uppercase tracking-[0.1em] text-faint">Files</dt>
              <dd className="min-w-0 break-words font-mono text-xs text-susp">{e.attachments.join(", ")}</dd>
            </>
          ) : null}
        </dl>
      </div>
      <div className="relative mt-4 border-t border-hair">
        {/* pattern sits outside the scroller so it stays put while the email scrolls */}
        <DotPattern cx={1} cy={1} cr={1} className="fill-white/[0.08] [mask-image:radial-gradient(420px_circle_at_center,white,transparent)] md:fill-white/[0.08]" />
        <div className="thin-scroll relative max-h-[28rem] overflow-y-auto">
          <pre className="relative whitespace-pre-wrap break-words p-5 font-mono text-[13px] leading-relaxed text-ink/85 sm:p-6">
            {body
              ? segments.map((seg, i) =>
                  seg.notes.length ? (
                    <Tooltip key={i}>
                      <TooltipTrigger asChild>
                        <mark tabIndex={0} data-sev={topSeverity(seg.notes)} className="evidence-mark">
                          {seg.text}
                        </mark>
                      </TooltipTrigger>
                      <TooltipContent side="top" className="max-w-xs">
                        <ul className="flex flex-col gap-1">
                          {seg.notes.slice(0, 4).map((n, j) => (
                            <li key={j}>
                              <span className="font-mono text-[10px] uppercase opacity-70">
                                {n.severity} · {n.source}
                              </span>
                              <br />
                              {n.claim}
                            </li>
                          ))}
                        </ul>
                      </TooltipContent>
                    </Tooltip>
                  ) : (
                    <React.Fragment key={i}>{seg.text}</React.Fragment>
                  ),
                )
              : "(no plain-text body)"}
          </pre>
        </div>
      </div>
    </section>
  )
}

const SANDBOX_TONE: Record<string, string> = {
  "credential-harvest": "text-scam border-scam/40 bg-scam/10",
  "malware-drop": "text-scam border-scam/40 bg-scam/10",
  unreachable: "text-susp border-susp/40 bg-susp/10",
  blocked: "text-susp border-susp/40 bg-susp/10",
  benign: "text-safe border-safe/40 bg-safe/10",
}

function SandboxSection({ results }: { results: SandboxResult[] }) {
  return (
    <section className="hud p-5 sm:p-6" aria-labelledby="sandbox-title">
      <SectionTitle aside={<span className="text-xs text-faint">fetched with no JavaScript</span>}>
        <span id="sandbox-title">Link sandbox</span>
      </SectionTitle>
      <ul className="flex flex-col gap-2">
        {results.map((r, i) => (
          <li key={`${r.url}-${i}`} className="flex min-w-0 flex-col gap-1.5 rounded-xl border border-hair bg-black/25 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className={cn("rounded-full border px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.12em]", SANDBOX_TONE[r.kind] ?? SANDBOX_TONE.unreachable)}>
                {r.kind}
              </span>
              {r.status_code != null ? <span className="font-mono text-[11px] text-faint">HTTP {r.status_code}</span> : null}
              {r.has_password_form ? <span className="font-mono text-[11px] text-scam">password form</span> : null}
              {r.download_detected ? <span className="font-mono text-[11px] text-scam">download</span> : null}
            </div>
            <p className="flex min-w-0 items-center gap-1.5 font-mono text-[12px] text-ink/85">
              <Link2 className="size-3.5 shrink-0 text-faint" aria-hidden="true" />
              <span className="break-all">{r.url}</span>
            </p>
            {r.final_url && r.final_url !== r.url ? (
              <p className="flex min-w-0 items-center gap-1.5 font-mono text-[11.5px] text-muted-foreground">
                <ExternalLink className="size-3.5 shrink-0" aria-hidden="true" />
                <span className="break-all">lands on {r.final_url}</span>
              </p>
            ) : null}
            {r.redirect_chain?.length ? <p className="text-xs text-faint">{r.redirect_chain.length} redirect(s)</p> : null}
            {r.page_title ? <p className="text-xs text-muted-foreground">Page title: {r.page_title}</p> : null}
            {r.failure_reason ? <p className="text-xs text-faint">{r.failure_reason}</p> : null}
          </li>
        ))}
      </ul>
    </section>
  )
}

function ShareButton({ token }: { token: string | null }) {
  const [done, setDone] = React.useState(false)
  if (!token) return null
  return (
    <button
      type="button"
      onClick={() => {
        const url = `${window.location.origin}/share/${encodeURIComponent(token)}`
        navigator.clipboard.writeText(url).then(
          () => {
            setDone(true)
            toast.success("Share link copied", { description: "Anyone with the link can read this verdict." })
            window.setTimeout(() => setDone(false), 1800)
          },
          () => toast.error("Could not copy the link"),
        )
      }}
      className="inline-flex h-10 items-center gap-2 rounded-full border border-lime/40 bg-lime/5 px-4 text-sm font-medium text-lime transition-colors hover:bg-lime/15"
    >
      {done ? <CheckCircle2 className="size-4" /> : <Share2 className="size-4" />}
      {done ? "Link copied" : "Share verdict"}
    </button>
  )
}

function AbuseReportButton({ id }: { id: string }) {
  const [open, setOpen] = React.useState(false)
  const [md, setMd] = React.useState<string | null>(null)
  const [err, setErr] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(false)

  const load = React.useCallback(() => {
    setLoading(true)
    setErr(null)
    api
      .abuseReport(id)
      .then((r) => setMd(r.markdown))
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Could not build the report."))
      .finally(() => setLoading(false))
  }, [id])

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o)
        if (o && md === null) load()
      }}
    >
      <DialogTrigger asChild>
        <button
          type="button"
          className="inline-flex h-10 items-center gap-2 rounded-full border border-hair px-4 text-sm font-medium text-ink transition-colors hover:border-lime/40"
        >
          <FileWarning className="size-4 text-susp" /> Abuse report
        </button>
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-hidden border-hair bg-surface sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-display">Takedown-ready abuse report</DialogTitle>
          <DialogDescription>Indicators and cited evidence, ready to paste into a registrar or hosting abuse form.</DialogDescription>
        </DialogHeader>
        {loading ? (
          <div className="flex items-center gap-2 py-8 text-muted-foreground">
            <Loader2 className="size-4 animate-spin text-lime" /> Building report
          </div>
        ) : err ? (
          <p className="text-sm text-scam">{err}</p>
        ) : md ? (
          <>
            <pre className="thin-scroll max-h-[52vh] overflow-auto whitespace-pre-wrap break-words rounded-xl border border-hair bg-black/40 p-4 font-mono text-[12px] leading-relaxed text-ink/90">
              {md}
            </pre>
            <button
              type="button"
              onClick={() =>
                navigator.clipboard.writeText(md).then(
                  () => toast.success("Report copied"),
                  () => toast.error("Could not copy"),
                )
              }
              className="inline-flex h-10 items-center gap-2 self-start rounded-full bg-lime px-5 text-sm font-semibold text-black"
            >
              <Copy className="size-4" /> Copy markdown
            </button>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
