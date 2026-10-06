"use client"

import * as React from "react"
import Link from "next/link"
import { ArrowLeft } from "lucide-react"

import { ErrorState, LoadingState } from "@/components/aegis/bits"
import { PipelineView } from "@/components/aegis/pipeline-view"
import { VerdictReport } from "@/components/aegis/verdict-report"
import { api, ApiError, type Analysis, type Stage, type StageEvent } from "@/lib/api"
import { timeAgo } from "@/lib/format"

type Phase = "loading" | "live" | "done" | "failed" | "missing" | "error"

function stagesFrom(list: Stage[] | undefined): Record<string, Stage> {
  const out: Record<string, Stage> = {}
  for (const s of list ?? []) out[s.name] = s
  return out
}

export function CaseView({ id }: { id: string }) {
  const [analysis, setAnalysis] = React.useState<Analysis | null>(null)
  const [stages, setStages] = React.useState<Record<string, Stage>>({})
  const [phase, setPhase] = React.useState<Phase>("loading")
  const [error, setError] = React.useState<string | null>(null)
  const [attempt, setAttempt] = React.useState(0)

  React.useEffect(() => {
    let alive = true
    let es: EventSource | null = null
    let poll = 0

    const finish = async () => {
      try {
        const full = await api.analysis(id)
        if (!alive) return
        setAnalysis(full)
        setStages(stagesFrom(full.stages))
        setPhase(full.status === "failed" ? "failed" : full.status === "done" ? "done" : "live")
        return full
      } catch (e) {
        if (!alive) return
        setError(e instanceof Error ? e.message : "Could not load the analysis.")
        setPhase("error")
      }
    }

    // Fallback when the event stream drops: poll until the analysis settles.
    const startPolling = () => {
      if (poll) return
      poll = window.setInterval(async () => {
        const full = await finish()
        if (full && (full.status === "done" || full.status === "failed")) {
          window.clearInterval(poll)
          poll = 0
        }
      }, 3000)
    }

    const subscribe = () => {
      es = new EventSource(api.eventsUrl(id))
      es.addEventListener("stage", (ev) => {
        try {
          const s = JSON.parse((ev as MessageEvent).data) as StageEvent
          setStages((prev) => ({ ...prev, [s.name]: { ...prev[s.name], ...s } }))
        } catch {
          /* ignore malformed event */
        }
      })
      // The done payload only carries the label; the full fetch is authoritative.
      es.addEventListener("done", () => {
        es?.close()
        es = null
        void finish()
      })
      es.onerror = () => {
        es?.close()
        es = null
        if (alive) startPolling()
      }
    }

    ;(async () => {
      try {
        const first = await api.analysis(id)
        if (!alive) return
        setAnalysis(first)
        setStages(stagesFrom(first.stages))
        if (first.status === "done") setPhase("done")
        else if (first.status === "failed") setPhase("failed")
        else {
          setPhase("live")
          subscribe()
        }
      } catch (e) {
        if (!alive) return
        if (e instanceof ApiError && e.status === 404) setPhase("missing")
        else {
          setError(e instanceof Error ? e.message : "Could not load the analysis.")
          setPhase("error")
        }
      }
    })()

    return () => {
      alive = false
      es?.close()
      if (poll) window.clearInterval(poll)
    }
  }, [id, attempt])

  const header = (
    <div className="mb-6 flex flex-col gap-3">
      <Link href="/cases" className="inline-flex w-fit items-center gap-1.5 font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground hover:text-lime">
        <ArrowLeft className="size-3.5" /> All cases
      </Link>
      {analysis ? (
        <div className="min-w-0">
          <h1 className="font-display text-2xl font-bold tracking-tight text-ink sm:text-3xl">
            <span className="break-words">{analysis.subject || analysis.email?.subject || "(no subject)"}</span>
          </h1>
          <p className="mt-1 break-words font-mono text-xs text-muted-foreground">
            {analysis.sender || analysis.email?.from || "unknown sender"} · {timeAgo(analysis.created_at)} · {analysis.source} · {analysis.id}
          </p>
        </div>
      ) : null}
    </div>
  )

  if (phase === "loading") {
    return (
      <div>
        {header}
        <LoadingState label="Loading analysis" />
      </div>
    )
  }
  if (phase === "missing") {
    return (
      <div>
        {header}
        <ErrorState message="No analysis with this id exists. It may have been typed wrong." />
      </div>
    )
  }
  if (phase === "error") {
    return (
      <div>
        {header}
        <ErrorState message={error ?? "Something went wrong."} onRetry={() => setAttempt((n) => n + 1)} />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      {header}
      <PipelineView stages={stages} live={phase === "live"} />
      {phase === "live" ? (
        <div className="hud flex flex-col items-center gap-2 px-6 py-12 text-center">
          <p className="font-display text-xl font-bold text-ink">The agents are working on it.</p>
          <p className="max-w-lg text-sm text-muted-foreground">
            Each card above lights up as its agent finishes. A full analysis usually takes 15 to 40 seconds; the verdict appears here automatically.
          </p>
        </div>
      ) : null}
      {phase === "failed" ? (
        <ErrorState message={analysis?.error || "The analysis failed. The pipeline fails closed, so treat this email as suspicious."} />
      ) : null}
      {phase === "done" && analysis ? <VerdictReport analysis={analysis} /> : null}
    </div>
  )
}
