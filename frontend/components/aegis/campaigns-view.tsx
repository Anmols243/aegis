"use client"

import * as React from "react"
import dynamic from "next/dynamic"
import type { NodeObject } from "react-force-graph-2d"
import Link from "next/link"

import { EmptyState, ErrorState, LoadingState, VerdictBadge } from "@/components/aegis/bits"
import { api, type CampaignsResponse, type GraphNode } from "@/lib/api"
import { LABEL_META } from "@/lib/format"
import { cn } from "@/lib/utils"

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
  loading: () => <LoadingState label="Drawing the graph" />,
})

const KIND_COLOR: Record<string, string> = {
  sender: "#9ec5ff",
  domain: "#d9ff3d",
  url: "#c6a8ff",
  phone: "#7ee8fa",
  template: "#8a8f98",
}

type FGNode = GraphNode & { x?: number; y?: number }

// Canvas cannot resolve CSS variables, so verdict colors are repeated as hex (same values as globals.css).
const VERDICT_HEX: Record<string, string> = { SCAM: "#ff5c5c", SUSPICIOUS: "#ffb224", LIKELY_SAFE: "#3ddc97" }

function nodeColor(n: GraphNode): string {
  if (n.kind === "analysis") return (n.verdict && VERDICT_HEX[n.verdict]) || "#8a8f98"
  return KIND_COLOR[n.kind] ?? "#8a8f98"
}

export function CampaignsView() {
  const [data, setData] = React.useState<CampaignsResponse | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [attempt, setAttempt] = React.useState(0)
  const [selected, setSelected] = React.useState<FGNode | null>(null)
  const wrapRef = React.useRef<HTMLDivElement>(null)
  const [size, setSize] = React.useState({ w: 600, h: 460 })

  React.useEffect(() => {
    let alive = true
    api
      .campaigns()
      .then((d) => {
        if (alive) {
          setData(d)
          setError(null)
        }
      })
      .catch((e: unknown) => alive && setError(e instanceof Error ? e.message : "Could not load campaigns."))
    return () => {
      alive = false
    }
  }, [attempt])

  React.useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => {
      const w = Math.max(280, Math.round(entry.contentRect.width))
      setSize({ w, h: w < 640 ? 380 : 520 })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [data])

  // react-force-graph mutates link endpoints into node objects, so hand it a copy.
  const graphData = React.useMemo(
    () => (data ? { nodes: data.graph.nodes.map((n) => ({ ...n })), links: data.graph.links.map((l) => ({ ...l })) } : { nodes: [], links: [] }),
    [data],
  )

  const neighbours = React.useMemo(() => {
    if (!selected || !data) return []
    const ids = new Set<string>()
    for (const l of data.graph.links) {
      if (l.source === selected.id) ids.add(l.target)
      if (l.target === selected.id) ids.add(l.source)
    }
    return data.graph.nodes.filter((n) => ids.has(n.id))
  }, [selected, data])

  if (error && !data) return <ErrorState message={error} onRetry={() => setAttempt((n) => n + 1)} />
  if (!data) return <LoadingState label="Loading campaigns" />

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)]">
      <div className="flex min-w-0 flex-col gap-3">
        <div ref={wrapRef} className="hud overflow-hidden">
          {data.graph.nodes.length === 0 ? (
            <EmptyState title="No graph yet">Analyze a few emails; shared domains, senders and phones will link them here.</EmptyState>
          ) : (
            <ForceGraph2D
              graphData={graphData}
              width={size.w}
              height={size.h}
              backgroundColor="rgba(0,0,0,0)"
              cooldownTicks={120}
              linkColor={() => "rgba(255,255,255,0.14)"}
              linkWidth={1}
              nodeRelSize={4}
              nodeLabel={(node: NodeObject) => { const n = node as FGNode; return `${n.kind}: ${n.label}` }}
              onNodeClick={(node: NodeObject) => setSelected(node as FGNode)}
              onBackgroundClick={() => setSelected(null)}
              nodeCanvasObject={(node: NodeObject, ctx: CanvasRenderingContext2D, scale: number) => {
                const n = node as FGNode
                const isAnalysis = n.kind === "analysis"
                const r = isAnalysis ? 6 : 3.5
                const x = n.x ?? 0
                const y = n.y ?? 0
                const color = nodeColor(n)
                ctx.beginPath()
                ctx.arc(x, y, r, 0, Math.PI * 2)
                ctx.fillStyle = color
                ctx.shadowColor = color
                ctx.shadowBlur = isAnalysis ? 10 : 0
                ctx.fill()
                ctx.shadowBlur = 0
                if (selected && selected.id === n.id) {
                  ctx.lineWidth = 1.5 / scale
                  ctx.strokeStyle = "#ffffff"
                  ctx.beginPath()
                  ctx.arc(x, y, r + 3, 0, Math.PI * 2)
                  ctx.stroke()
                }
                // Labels only when zoomed in or selected: clustered labels overlap,
                // and hovering already shows a tooltip.
                if (scale > 2.4 || (selected && selected.id === n.id)) {
                  const text = n.label.length > 26 ? `${n.label.slice(0, 25)}...` : n.label
                  ctx.font = `${11 / scale}px ui-monospace, monospace`
                  ctx.fillStyle = isAnalysis ? "rgba(237,237,232,0.85)" : "rgba(138,143,152,0.9)"
                  ctx.textAlign = "center"
                  ctx.fillText(text, x, y + r + 10 / scale + 2)
                }
              }}
              nodePointerAreaPaint={(node: NodeObject, color: string, ctx: CanvasRenderingContext2D) => {
                const n = node as FGNode
                ctx.fillStyle = color
                ctx.beginPath()
                ctx.arc(n.x ?? 0, n.y ?? 0, 9, 0, Math.PI * 2)
                ctx.fill()
              }}
            />
          )}
        </div>
        <ul className="flex flex-wrap gap-3 text-xs text-muted-foreground" aria-label="Legend">
          {(["SCAM", "SUSPICIOUS", "LIKELY_SAFE"] as const).map((l) => (
            <li key={l} className="flex items-center gap-1.5">
              <span className="size-2.5 rounded-full" style={{ background: LABEL_META[l].color }} /> {LABEL_META[l].text} email
            </li>
          ))}
          {Object.entries(KIND_COLOR).map(([k, c]) => (
            <li key={k} className="flex items-center gap-1.5">
              <span className="size-2 rounded-full" style={{ background: c }} /> {k}
            </li>
          ))}
        </ul>

        {selected ? (
          <div className="hud p-4">
            <p className="label-mono mb-1">{selected.kind}</p>
            {selected.kind === "analysis" ? (
              <Link href={`/cases/${encodeURIComponent(selected.id.replace(/^a:/, ""))}`} className="break-words text-[15px] font-semibold text-ink hover:text-lime">
                {selected.label}
              </Link>
            ) : (
              <p className="break-all font-mono text-sm text-ink">{selected.label}</p>
            )}
            {neighbours.length ? (
              <p className="mt-2 text-xs text-muted-foreground">
                Connected to {neighbours.length} node{neighbours.length === 1 ? "" : "s"}:{" "}
                {neighbours
                  .slice(0, 6)
                  .map((n) => n.label)
                  .join(", ")}
                {neighbours.length > 6 ? ", ..." : ""}
              </p>
            ) : null}
          </div>
        ) : (
          <p className="text-xs text-faint">Click a node to see what it connects to. Drag to rearrange, scroll to zoom.</p>
        )}
      </div>

      <aside className="flex min-w-0 flex-col gap-3" aria-labelledby="camp-list">
        <h2 id="camp-list" className="label-mono text-ink/80">
          {data.campaigns.length} campaign{data.campaigns.length === 1 ? "" : "s"}
        </h2>
        {data.campaigns.length === 0 ? (
          <div className="hud">
            <EmptyState title="No campaigns yet">A campaign appears when two or more emails share infrastructure.</EmptyState>
          </div>
        ) : (
          data.campaigns.map((c) => (
            <section key={c.id} className="hud p-4">
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="font-mono text-sm font-semibold text-lime">{c.id}</span>
                <span className="font-mono text-xs text-faint">
                  {c.analyses.length} {c.analyses.length === 1 ? "email" : "emails"}
                  {c.hidden_count ? (
                    <span className="ml-1.5 text-muted-foreground" title="Emails from other people that share this infrastructure. Their content stays private.">
                      +{c.hidden_count} private
                    </span>
                  ) : null}
                </span>
              </div>
              <p className="text-sm text-muted-foreground">{c.explanation}</p>
              <ul className="mt-3 flex flex-wrap gap-1.5">
                {c.infra.slice(0, 8).map((i) => (
                  <li key={`${i.kind}:${i.value}`} className="max-w-full truncate rounded-md border border-hair bg-black/30 px-2 py-0.5 font-mono text-[11px] text-ink/80">
                    <span className="text-faint">{i.kind}</span> {i.value}
                  </li>
                ))}
              </ul>
              <ul className="mt-3 flex flex-col gap-1.5">
                {c.analyses.slice(0, 6).map((a) => (
                  <li key={a.id} className="flex min-w-0 items-center gap-2">
                    <VerdictBadge label={a.label} />
                    <Link href={`/cases/${encodeURIComponent(a.id)}`} className={cn("truncate text-sm text-ink hover:text-lime")}>
                      {a.subject || a.id}
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ))
        )}
      </aside>
    </div>
  )
}
