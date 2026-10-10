"use client"

import * as React from "react"
import Link from "next/link"
import { ArrowLeft, FileSearch } from "lucide-react"

import { ErrorState, LoadingState } from "@/components/aegis/bits"
import { HERO_SECONDARY, PageHero } from "@/components/aegis/page-hero"
import { PipelineView } from "@/components/aegis/pipeline-view"
import { useLiveAnalysis } from "@/components/aegis/use-live-analysis"
import { VerdictReport } from "@/components/aegis/verdict-report"
import { timeAgo } from "@/lib/format"

export function CaseView({ id }: { id: string }) {
  const { analysis, stages, phase, error, retry } = useLiveAnalysis(id)

  // The verdict panel below carries the moving streak, so this header goes without one.
  const header = (
    <PageHero
      className="mb-6"
      label="Case"
      icon={FileSearch}
      title={analysis ? analysis.subject || analysis.email?.subject || "(no subject)" : "Case"}
      accent={!analysis}
      beam={false}
      actions={
        <Link href="/cases" className={HERO_SECONDARY}>
          <ArrowLeft className="size-4 text-lime" aria-hidden="true" />
          All cases
        </Link>
      }
    >
      {analysis ? (
        <span className="break-words font-mono text-xs">
          {analysis.sender || analysis.email?.from || "unknown sender"} · {timeAgo(analysis.created_at)} · {analysis.source} · {analysis.id}
        </span>
      ) : null}
    </PageHero>
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
        <ErrorState message={error ?? "Something went wrong."} onRetry={retry} />
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
