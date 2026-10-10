"use client"

import * as React from "react"
import Link from "next/link"
import { CheckCircle2, Crosshair, Loader2, ShieldAlert } from "lucide-react"
import { toast } from "sonner"

import { EmptyState, ErrorState, LoadingState, SectionTitle, VerdictBadge } from "@/components/aegis/bits"
import { BorderBeam } from "@/components/ui/border-beam"
import { DotPattern } from "@/components/ui/dot-pattern"
import { api, ApiError, type RedteamRun, type RedteamRunListItem, type RedteamSummary, type Sample } from "@/lib/api"
import { score100, timeAgo } from "@/lib/format"
import { cn } from "@/lib/utils"

export function RedteamArena() {
  const [samples, setSamples] = React.useState<Sample[] | null>(null)
  const [sampleId, setSampleId] = React.useState<string>("")
  const [n, setN] = React.useState(5)
  const [starting, setStarting] = React.useState(false)
  const [runId, setRunId] = React.useState<string | null>(null)
  const [run, setRun] = React.useState<RedteamRun | null>(null)
  const [runError, setRunError] = React.useState<string | null>(null)
  const [summary, setSummary] = React.useState<RedteamSummary | null>(null)
  const [runs, setRuns] = React.useState<RedteamRunListItem[] | null>(null)
  const [loadError, setLoadError] = React.useState<string | null>(null)

  const refreshSide = React.useCallback(() => {
    api.redteamSummary().then(setSummary).catch(() => undefined)
    api.redteamRuns().then(setRuns).catch(() => undefined)
  }, [])

  React.useEffect(() => {
    api
      .samples()
      .then((s) => {
        // Only scams make sense as red-team seeds.
        const scams = s.filter((x) => x.expected !== "LIKELY_SAFE")
        setSamples(scams)
        if (scams[0]) setSampleId(scams[0].id)
      })
      .catch((e: unknown) => setLoadError(e instanceof Error ? e.message : "Could not load samples."))
    refreshSide()
  }, [refreshSide])

  // Poll the active run every 2s until it finishes.
  React.useEffect(() => {
    if (!runId) return
    let alive = true
    let timer = 0
    const tick = async () => {
      try {
        const r = await api.redteamRun(runId)
        if (!alive) return
        setRun(r)
        setRunError(null)
        if (r.status === "done") {
          refreshSide()
          return
        }
      } catch (e) {
        if (!alive) return
        setRunError(e instanceof Error ? e.message : "Lost track of the run.")
        if (e instanceof ApiError && e.status === 404) return   // run is gone: stop polling
      }
      timer = window.setTimeout(tick, 2000)
    }
    void tick()
    return () => {
      alive = false
      window.clearTimeout(timer)
    }
  }, [runId, refreshSide])

  const start = async () => {
    if (!sampleId) return
    setStarting(true)
    setRun(null)
    try {
      const { id } = await api.createRedteamRun({ sample_id: sampleId, n })
      setRunId(id)
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not start the run.")
    } finally {
      setStarting(false)
    }
  }

  const axisRows = summary ? Object.entries(summary.by_axis).sort((a, b) => b[1].total - a[1].total) : []
  const maxAxis = Math.max(1, ...axisRows.map(([, v]) => v.total))

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
      <div className="flex min-w-0 flex-col gap-6">
        <BorderBeam className="min-w-0 rounded-[1.25rem]" radius={20} duration={8}>
          <div className="hud flex flex-col gap-4 p-5 sm:p-6">
            <SectionTitle>Launch an attack round</SectionTitle>
            {loadError ? (
              <ErrorState message={loadError} />
            ) : !samples ? (
              <LoadingState label="Loading seeds" />
            ) : samples.length === 0 ? (
              <EmptyState title="No scam samples available" />
            ) : (
              <>
                <div role="radiogroup" aria-label="Seed scam" className="flex flex-wrap gap-2">
                  {samples.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      role="radio"
                      aria-checked={sampleId === s.id}
                      data-active={sampleId === s.id}
                      onClick={() => setSampleId(s.id)}
                      className="chip max-w-full whitespace-normal text-left"
                      title={s.description}
                    >
                      {s.title}
                    </button>
                  ))}
                </div>
                <div className="flex flex-wrap items-center gap-4">
                  <label className="flex items-center gap-3 text-sm text-muted-foreground">
                    Variants
                    <input
                      type="range"
                      min={1}
                      max={8}
                      value={n}
                      onChange={(e) => setN(Number(e.target.value))}
                      className="w-36 accent-[var(--aegis-lime)]"
                    />
                    <span className="w-4 font-mono text-ink">{n}</span>
                  </label>
                  <button
                    type="button"
                    onClick={start}
                    disabled={starting || (run !== null && run.status !== "done")}
                    className="inline-flex h-11 items-center gap-2 rounded-full bg-lime px-6 text-sm font-semibold text-black transition-transform active:scale-[0.98] disabled:opacity-60"
                  >
                    {starting ? <Loader2 className="size-4 animate-spin" /> : <Crosshair className="size-4" />}
                    Mutate and attack
                  </button>
                </div>
                <p className="text-xs text-faint">
                  The engine is deterministic (seeded), no AI writes the phishing. Each variant runs through the full pipeline; a variant is caught when
                  it is still called SCAM.
                </p>
              </>
            )}
          </div>
        </BorderBeam>

        {runError ? <ErrorState message={runError} /> : null}

        {run ? (
          <section aria-labelledby="run-title" className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <h2 id="run-title" className="label-mono text-ink/80">
                Run {run.id}
              </h2>
              <span className="font-mono text-xs text-muted-foreground">
                {run.summary.caught} caught · {run.summary.missed} missed · {run.summary.pending} pending
              </span>
              {run.status !== "done" ? <Loader2 className="size-3.5 animate-spin text-lime" aria-label="running" /> : null}
            </div>
            <ul className="grid gap-3 md:grid-cols-2">
              {run.variants.map((v) => (
                <li
                  key={v.index}
                  className={cn(
                    "hud flex min-w-0 flex-col gap-2.5 p-4",
                    v.caught === true && "border-safe/30",
                    v.caught === false && "border-scam/40",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs text-faint">variant {v.index + 1}</span>
                    {v.caught === true ? (
                      <span className="inline-flex items-center gap-1 font-mono text-[11px] uppercase tracking-[0.12em] text-safe">
                        <CheckCircle2 className="size-3.5" /> caught
                      </span>
                    ) : v.caught === false ? (
                      <span className="inline-flex items-center gap-1 font-mono text-[11px] uppercase tracking-[0.12em] text-scam">
                        <ShieldAlert className="size-3.5" /> missed
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 font-mono text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                        <Loader2 className="size-3.5 animate-spin" /> {v.status}
                      </span>
                    )}
                  </div>
                  <ul className="flex flex-wrap gap-1.5">
                    {v.axes.map((ax) => (
                      <li key={ax} className="rounded-full border border-lime/30 bg-lime/5 px-2 py-0.5 font-mono text-[10.5px] text-lime">
                        {ax}
                      </li>
                    ))}
                  </ul>
                  <div className="relative overflow-hidden rounded-lg border border-hair">
                    <DotPattern className="fill-white/[0.06] [mask-image:radial-gradient(240px_circle_at_center,white,transparent)] md:fill-white/[0.06]" />
                    <pre className="thin-scroll relative max-h-36 overflow-y-auto whitespace-pre-wrap break-words p-3 font-mono text-[11.5px] leading-relaxed text-ink/75">
                      {v.text}
                    </pre>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <VerdictBadge label={v.label} />
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-sm tabular-nums text-ink/80">{score100(v.score)}</span>
                      {v.analysis_id ? (
                        <Link href={`/cases/${encodeURIComponent(v.analysis_id)}`} className="text-xs text-lime hover:underline">
                          evidence
                        </Link>
                      ) : null}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ) : (
          // Fills the column until a round runs, so it lines up with the scoreboard beside it.
          <section aria-label="Results" className="hud flex min-h-48 flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
            <Crosshair className="size-5 text-lime" aria-hidden="true" />
            <p className="label-mono text-[12px] text-muted-foreground">Results</p>
            <p className="max-w-sm text-sm text-faint">Pick a seed and launch a round. Each disguised variant shows up here as it runs, marked caught or missed.</p>
          </section>
        )}
      </div>

      <aside className="flex min-w-0 flex-col gap-6">
        <section className="hud p-5" aria-labelledby="totals-title">
          <SectionTitle>
            <span id="totals-title">All-time scoreboard</span>
          </SectionTitle>
          {!summary ? (
            <LoadingState label="Loading" />
          ) : (
            <>
              <div className="grid grid-cols-3 gap-2 text-center">
                {[
                  ["variants", summary.variants, "text-ink"],
                  ["caught", summary.caught, "text-safe"],
                  ["missed", summary.missed, "text-scam"],
                ].map(([k, val, tone]) => (
                  <div key={k as string} className="rounded-xl border border-hair bg-black/25 py-3">
                    <p className={cn("font-mono text-2xl tabular-nums", tone as string)}>{val as number}</p>
                    <p className="label-mono">{k as string}</p>
                  </div>
                ))}
              </div>
              {axisRows.length ? (
                <ul className="mt-5 flex flex-col gap-2.5" aria-label="Misses by mutation axis">
                  {axisRows.map(([axis, v]) => (
                    <li key={axis} className="flex flex-col gap-1">
                      <div className="flex items-center justify-between gap-2 text-xs">
                        <span className="truncate font-mono text-muted-foreground">{axis}</span>
                        <span className="font-mono tabular-nums text-ink/80">
                          {v.missed}/{v.total} missed
                        </span>
                      </div>
                      <div className="flex h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                        <div className="h-full bg-safe" style={{ width: `${((v.total - v.missed) / maxAxis) * 100}%` }} />
                        <div className="h-full bg-scam" style={{ width: `${(v.missed / maxAxis) * 100}%` }} />
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-4 text-sm text-faint">No variants yet. Launch a round to fill the board.</p>
              )}
            </>
          )}
        </section>

        <section className="hud p-5" aria-labelledby="runs-title">
          <SectionTitle>
            <span id="runs-title">Recent rounds</span>
          </SectionTitle>
          {!runs ? (
            <LoadingState label="Loading" />
          ) : runs.length === 0 ? (
            <p className="text-sm text-faint">None yet.</p>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {runs.slice(0, 8).map((r) => (
                <li key={r.id}>
                  <button
                    type="button"
                    onClick={() => setRunId(r.id)}
                    className={cn(
                      "flex w-full items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left text-xs transition-colors hover:border-lime/40",
                      runId === r.id ? "border-lime/50 bg-lime/5" : "border-hair",
                    )}
                  >
                    <span className="truncate font-mono text-ink/85">{r.id}</span>
                    <span className="shrink-0 font-mono text-muted-foreground">
                      {r.summary.caught}/{r.summary.total} · {timeAgo(r.created_at)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </aside>
    </div>
  )
}
