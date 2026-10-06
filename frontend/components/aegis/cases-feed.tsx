"use client"

import * as React from "react"
import Link from "next/link"
import { Loader2, Mail, Search } from "lucide-react"

import { EmptyState, ErrorState, LoadingState, VerdictBadge } from "@/components/aegis/bits"
import { PrivateBadge } from "@/components/aegis/privacy-promises"
import { api, type AnalysisSummary, type Label } from "@/lib/api"
import { LABEL_META, score100, seconds, timeAgo } from "@/lib/format"

const FILTERS: { key: Label | null; text: string }[] = [
  { key: null, text: "All" },
  { key: "SCAM", text: "Scam" },
  { key: "SUSPICIOUS", text: "Suspicious" },
  { key: "LIKELY_SAFE", text: "Safe" },
]

export function CasesFeed() {
  const [label, setLabel] = React.useState<Label | null>(null)
  const [mine, setMine] = React.useState(false)
  const [mineReady, setMineReady] = React.useState(false)
  const [query, setQuery] = React.useState("")
  const [q, setQ] = React.useState("")
  const [items, setItems] = React.useState<AnalysisSummary[] | null>(null)
  const [cursor, setCursor] = React.useState<string | null>(null)
  const [error, setError] = React.useState<string | null>(null)
  const [loadingMore, setLoadingMore] = React.useState(false)
  const [attempt, setAttempt] = React.useState(0)

  // /cases?mine=true (linked from the Inbox page) opens with the Mine filter on.
  React.useEffect(() => {
    setMine(new URLSearchParams(window.location.search).get("mine") === "true")
    setMineReady(true)
  }, [])

  // Debounce the search box.
  React.useEffect(() => {
    const t = window.setTimeout(() => setQ(query.trim()), 300)
    return () => window.clearTimeout(t)
  }, [query])

  React.useEffect(() => {
    if (!mineReady) return
    let alive = true
    api
      .listAnalyses({ limit: 20, label, q, mine })
      .then((page) => {
        if (!alive) return
        setItems(page.items)
        setCursor(page.next_cursor)
        setError(null)
      })
      .catch((e: unknown) => alive && setError(e instanceof Error ? e.message : "Could not load cases."))
    return () => {
      alive = false
    }
  }, [label, q, mine, mineReady, attempt])

  const loadMore = async () => {
    if (!cursor) return
    setLoadingMore(true)
    try {
      const page = await api.listAnalyses({ limit: 20, label, q, cursor, mine })
      setItems((prev) => [...(prev ?? []), ...page.items])
      setCursor(page.next_cursor)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load more.")
    } finally {
      setLoadingMore(false)
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div role="group" aria-label="Filter by verdict" className="flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <button
              key={f.text}
              type="button"
              className="chip"
              data-active={label === f.key}
              aria-pressed={label === f.key}
              onClick={() => {
                setItems(null)
                setLabel(f.key)
              }}
            >
              {f.text}
            </button>
          ))}
          <span className="mx-1 hidden h-6 w-px self-center bg-hair sm:block" aria-hidden="true" />
          <button
            type="button"
            className="chip"
            data-active={mine}
            aria-pressed={mine}
            title="Only emails you analyzed from this browser, including your connected mailboxes"
            onClick={() => {
              setItems(null)
              setMine((m) => !m)
            }}
          >
            Mine
          </button>
        </div>
        <label className="flex items-center gap-2 rounded-full border border-hair bg-surface/90 px-4 py-2 focus-within:border-lime/50 sm:ml-auto sm:w-72">
          <Search className="size-4 shrink-0 text-faint" aria-hidden="true" />
          <span className="sr-only">Search sender or subject</span>
          <input
            value={query}
            onChange={(e) => {
              setItems(null)
              setQuery(e.target.value)
            }}
            placeholder="Search sender or subject"
            className="min-w-0 flex-1 bg-transparent font-mono text-[13px] text-ink placeholder:text-faint focus:outline-none"
          />
        </label>
      </div>

      {error && !items ? (
        <ErrorState message={error} onRetry={() => setAttempt((n) => n + 1)} />
      ) : !items ? (
        <LoadingState label="Loading cases" />
      ) : items.length === 0 ? (
        <div className="hud">
          <EmptyState title={q || label || mine ? "No matching cases" : "No cases yet"}>
            {mine && !q && !label ? (
              <>
                Emails you paste or receive in a{" "}
                <Link href="/inbox" className="text-lime hover:underline">
                  connected mailbox
                </Link>{" "}
                show up here, visible only to this browser.
              </>
            ) : q || label ? (
              "Try another filter or search term."
            ) : (
              <>
                Analyze your first email on the{" "}
                <Link href="/analyze" className="text-lime hover:underline">
                  Analyze
                </Link>{" "}
                page.
              </>
            )}
          </EmptyState>
        </div>
      ) : (
        <>
          <ul className="flex flex-col gap-2.5">
            {items.map((a) => (
              <li key={a.id}>
                <Link href={`/cases/${encodeURIComponent(a.id)}`} className="hud hud-interactive flex min-w-0 items-center gap-4 p-4 sm:p-5">
                  <div className="min-w-0 flex-1">
                    <div className="flex min-w-0 items-center gap-3">
                      <VerdictBadge label={a.label} />
                      <span className="truncate text-[15px] font-semibold text-ink">{a.subject || "(no subject)"}</span>
                      {a.mailbox_id ? (
                        <span
                          className="inline-flex shrink-0 items-center gap-1 rounded-full border border-lime/30 px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.12em] text-lime"
                          title="From your connected mailbox"
                        >
                          <Mail className="size-3" aria-hidden="true" />
                          Mailbox
                        </span>
                      ) : null}
                      {a.visibility === "private" ? <PrivateBadge className="hidden sm:inline-flex" /> : null}
                    </div>
                    <p className="mt-1.5 truncate font-mono text-[11.5px] text-muted-foreground">
                      {a.sender || "unknown sender"} · {timeAgo(a.created_at)} · {a.source}
                      {a.status !== "done" ? ` · ${a.status}` : ""}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <span className="font-mono text-lg font-semibold tabular-nums" style={{ color: a.label ? LABEL_META[a.label].color : undefined }}>
                      {score100(a.score)}
                    </span>
                    <span className="font-mono text-[10px] text-faint">{a.duration_s != null ? seconds(a.duration_s) : ""}</span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
          {error ? <p className="text-sm text-scam">{error}</p> : null}
          {cursor ? (
            <button type="button" onClick={loadMore} disabled={loadingMore} className="chip mx-auto inline-flex items-center gap-2">
              {loadingMore ? <Loader2 className="size-3.5 animate-spin" /> : null}
              Load more
            </button>
          ) : null}
        </>
      )}
    </div>
  )
}
