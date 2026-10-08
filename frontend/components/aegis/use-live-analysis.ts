"use client"

import * as React from "react"

import { api, ApiError, type Analysis, type Stage, type StageEvent } from "@/lib/api"

export type Phase = "loading" | "live" | "done" | "failed" | "missing" | "error"

function stagesFrom(list: Stage[] | undefined): Record<string, Stage> {
  const out: Record<string, Stage> = {}
  for (const s of list ?? []) out[s.name] = s
  return out
}

/** One analysis, kept live: stage events stream in over SSE, with polling as the fallback.
 *  Key the calling component by id: state is not reset when the id changes. */
export function useLiveAnalysis(id: string | null) {
  const [analysis, setAnalysis] = React.useState<Analysis | null>(null)
  const [stages, setStages] = React.useState<Record<string, Stage>>({})
  const [phase, setPhase] = React.useState<Phase>("loading")
  const [error, setError] = React.useState<string | null>(null)
  const [attempt, setAttempt] = React.useState(0)

  React.useEffect(() => {
    if (!id) return
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

  const retry = () => {
    setError(null)
    setPhase("loading")
    setAttempt((n) => n + 1)
  }

  return { analysis, stages, phase, error, retry }
}
