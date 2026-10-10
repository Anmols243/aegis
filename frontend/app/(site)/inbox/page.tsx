"use client"

import { useCallback, useEffect, useMemo, useState } from "react"

import { api, type Analysis, type AnalysisSummary, type Mailbox } from "@/lib/api"

function labelClass(label: AnalysisSummary["label"]) {
  if (label === "SCAM") {
    return "border-red-500/30 bg-red-500/10 text-red-300"
  }

  if (label === "SUSPICIOUS") {
    return "border-yellow-500/30 bg-yellow-500/10 text-yellow-300"
  }

  if (label === "LIKELY_SAFE") {
    return "border-lime/30 bg-lime/10 text-lime"
  }

  return "border-white/10 bg-white/5 text-muted-foreground"
}

function statusClass(status: Mailbox["status"]) {
  if (status === "active") return "text-lime"
  if (status === "error") return "text-red-400"
  if (status === "paused") return "text-yellow-400"
  return "text-muted-foreground"
}

export default function InboxPage() {
  const [mailboxes, setMailboxes] = useState<Mailbox[]>([])
  const [messages, setMessages] = useState<AnalysisSummary[]>([])
  const [selected, setSelected] = useState<Analysis | null>(null)

  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [connecting, setConnecting] = useState(false)
  const [checking, setChecking] = useState(false)
  const [disconnecting, setDisconnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const mailbox = mailboxes[0] ?? null

  const load = useCallback(async () => {
    try {
      setError(null)

      const [boxes, analyses] = await Promise.all([
        api.listMailboxes(),
        api.listAnalyses({
          limit: 100,
          mine: true,
        }),
      ])

      setMailboxes(boxes)

      const mailboxMessages = analyses.items.filter(
        (item) => item.source === "mailbox",
      )

      setMessages(mailboxMessages)

      if (selected) {
        const stillExists = mailboxMessages.some(
          (item) => item.id === selected.id,
        )

        if (!stillExists) {
          setSelected(null)
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load inbox.")
    } finally {
      setLoading(false)
    }
  }, [selected])

  useEffect(() => {
    void load()
  }, [load])

  const connectGoogle = async () => {
    try {
      setConnecting(true)
      setError(null)

      const result = await api.startOAuth("google", 7)

      window.location.href = result.url
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not start Google sign-in.",
      )
      setConnecting(false)
    }
  }

  const refreshInbox = async () => {
    try {
      setRefreshing(true)
      setError(null)
      await load()
    } finally {
      setRefreshing(false)
    }
  }

  const checkMail = async () => {
    if (!mailbox) return

    try {
      setChecking(true)
      setError(null)

      await api.checkMailbox(mailbox.id)

      await new Promise((resolve) => setTimeout(resolve, 1000))
      await load()
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not check the mailbox.",
      )
    } finally {
      setChecking(false)
    }
  }

  const disconnectGoogle = async () => {
    if (!mailbox) return

    const confirmed = window.confirm(
      "Disconnect this Gmail account from AEGIS?",
    )

    if (!confirmed) return

    try {
      setDisconnecting(true)
      setError(null)

      await api.removeMailbox(mailbox.id, false)

      setMailboxes([])
      setMessages([])
      setSelected(null)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not disconnect Gmail.",
      )
    } finally {
      setDisconnecting(false)
    }
  }

  const openAnalysis = async (id: string) => {
    try {
      setError(null)
      const result = await api.analysis(id)
      setSelected(result)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not load this analysis.",
      )
    }
  }

  const sortedMessages = useMemo(
    () =>
      [...messages].sort(
        (a, b) =>
          new Date(b.created_at).getTime() -
          new Date(a.created_at).getTime(),
      ),
    [messages],
  )

  return (
    <main className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-8">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-lime">
          AEGIS / MAILBOX
        </p>

        <div className="mt-2 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="font-display text-3xl font-extrabold tracking-tight text-ink sm:text-4xl">
              Gmail Inbox
            </h1>

            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
              Connect Gmail and analyze incoming messages through AEGIS.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void refreshInbox()}
              disabled={refreshing || loading}
              className="rounded-full border border-white/10 px-4 py-2 font-mono text-xs font-semibold uppercase tracking-[0.12em] text-ink transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {refreshing ? "Refreshing..." : "Refresh"}
            </button>

            {mailbox && (
              <button
                type="button"
                onClick={() => void checkMail()}
                disabled={checking}
                className="rounded-full bg-lime px-4 py-2 font-mono text-xs font-bold uppercase tracking-[0.12em] text-black transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {checking ? "Checking..." : "Check Gmail"}
              </button>
            )}
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {!loading && !mailbox && (
        <section className="rounded-2xl border border-white/10 bg-white/[0.02] p-8">
          <div className="max-w-xl">
            <p className="font-mono text-xs uppercase tracking-[0.18em] text-muted-foreground">
              Gmail not connected
            </p>

            <h2 className="mt-3 font-display text-2xl font-bold text-ink">
              Connect your Gmail account
            </h2>

            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              Sign in with Google to bring your Gmail messages into AEGIS.
            </p>

            <button
              type="button"
              onClick={() => void connectGoogle()}
              disabled={connecting}
              className="mt-6 rounded-full bg-lime px-5 py-2.5 font-mono text-xs font-bold uppercase tracking-[0.12em] text-black transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {connecting ? "Connecting..." : "Connect Google"}
            </button>
          </div>
        </section>
      )}

      {mailbox && (
        <>
          <section className="mb-6 rounded-2xl border border-white/10 bg-white/[0.02] p-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                  Connected account
                </p>

                <div className="mt-1 flex flex-wrap items-center gap-3">
                  <span className="font-mono text-sm text-ink">
                    {mailbox.email}
                  </span>

                  <span
                    className={`font-mono text-[10px] font-bold uppercase tracking-[0.15em] ${statusClass(mailbox.status)}`}
                  >
                    ● {mailbox.status}
                  </span>
                </div>

                <p className="mt-1 text-xs text-muted-foreground">
                  {mailbox.scanned} messages scanned · {mailbox.flagged} flagged
                </p>
              </div>

              <button
                type="button"
                onClick={() => void disconnectGoogle()}
                disabled={disconnecting}
                className="rounded-full border border-red-500/20 px-4 py-2 font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-red-300 transition hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {disconnecting ? "Disconnecting..." : "Disconnect Google"}
              </button>
            </div>

            {mailbox.last_error && (
              <div className="mt-4 rounded-lg border border-red-500/20 bg-red-500/5 px-3 py-2 text-xs text-red-300">
                {mailbox.last_error}
              </div>
            )}
          </section>

          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <section className="min-w-0 rounded-2xl border border-white/10 bg-white/[0.02]">
              <div className="border-b border-white/10 px-5 py-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                      Messages
                    </p>
                    <h2 className="mt-1 font-display text-xl font-bold text-ink">
                      AEGIS Inbox
                    </h2>
                  </div>

                  <span className="font-mono text-xs text-muted-foreground">
                    {sortedMessages.length}
                  </span>
                </div>
              </div>

              <div className="max-h-[650px] overflow-y-auto">
                {sortedMessages.length === 0 ? (
                  <div className="px-5 py-12 text-center">
                    <p className="text-sm text-muted-foreground">
                      No Gmail messages have been analyzed yet.
                    </p>

                    <button
                      type="button"
                      onClick={() => void checkMail()}
                      disabled={checking}
                      className="mt-4 rounded-full border border-white/10 px-4 py-2 font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-ink hover:bg-white/5 disabled:opacity-50"
                    >
                      {checking ? "Checking..." : "Check Gmail"}
                    </button>
                  </div>
                ) : (
                  sortedMessages.map((message) => (
                    <button
                      key={message.id}
                      type="button"
                      onClick={() => void openAnalysis(message.id)}
                      className={`block w-full border-b border-white/5 px-5 py-4 text-left transition hover:bg-white/[0.04] ${
                        selected?.id === message.id
                          ? "bg-white/[0.05]"
                          : ""
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-ink">
                            {message.subject || "(No subject)"}
                          </p>

                          <p className="mt-1 truncate font-mono text-[11px] text-muted-foreground">
                            {message.sender || "Unknown sender"}
                          </p>
                        </div>

                        {message.label && (
                          <span
                            className={`shrink-0 rounded-full border px-2 py-1 font-mono text-[9px] font-bold uppercase tracking-[0.1em] ${labelClass(message.label)}`}
                          >
                            {message.label.replace("_", " ")}
                          </span>
                        )}
                      </div>

                      <div className="mt-2 flex items-center justify-between gap-3">
                        <span className="font-mono text-[10px] text-muted-foreground">
                          {new Date(message.created_at).toLocaleString()}
                        </span>

                        <span className="font-mono text-[10px] uppercase text-muted-foreground">
                          {message.status}
                        </span>
                      </div>
                    </button>
                  ))
                )}
              </div>
            </section>

            <section className="min-w-0 rounded-2xl border border-white/10 bg-white/[0.02]">
              <div className="border-b border-white/10 px-5 py-4">
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                  AEGIS Analysis
                </p>

                <h2 className="mt-1 font-display text-xl font-bold text-ink">
                  {selected ? "Investigation" : "Select a message"}
                </h2>
              </div>

              {!selected ? (
                <div className="flex min-h-[500px] items-center justify-center px-6 text-center">
                  <p className="max-w-sm text-sm leading-6 text-muted-foreground">
                    Select an email from the inbox to view its AEGIS verdict,
                    score, confidence, evidence, and pipeline results.
                  </p>
                </div>
              ) : (
                <div className="max-h-[650px] overflow-y-auto p-5">
                  <div className="rounded-xl border border-white/10 bg-black/20 p-4">
                    <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      Verdict
                    </p>

                    <div className="mt-3 flex flex-wrap items-center gap-3">
                      <span
                        className={`rounded-full border px-3 py-1.5 font-mono text-xs font-bold tracking-[0.1em] ${labelClass(selected.verdict?.label ?? null)}`}
                      >
                        {selected.verdict?.label ?? selected.label ?? "PENDING"}
                      </span>

                      {selected.verdict && (
                        <>
                          <span className="font-mono text-xs text-muted-foreground">
                            Risk {Math.round(selected.verdict.score * 100)}%
                          </span>

                          <span className="font-mono text-xs text-muted-foreground">
                            Confidence{" "}
                            {Math.round(selected.verdict.confidence * 100)}%
                          </span>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="mt-5">
                    <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      Email
                    </p>

                    <h3 className="mt-2 text-lg font-semibold text-ink">
                      {selected.email.subject || "(No subject)"}
                    </h3>

                    <div className="mt-3 space-y-1 font-mono text-xs text-muted-foreground">
                      <p>FROM: {selected.email.from}</p>
                      <p>TO: {selected.email.to}</p>
                      {selected.email.reply_to && (
                        <p>REPLY-TO: {selected.email.reply_to}</p>
                      )}
                    </div>
                  </div>

                  {selected.summary && (
                    <div className="mt-5">
                      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                        Summary
                      </p>

                      <p className="mt-2 text-sm leading-6 text-muted-foreground">
                        {selected.summary}
                      </p>
                    </div>
                  )}

                  {selected.red_flags.length > 0 && (
                    <div className="mt-5">
                      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                        Red flags
                      </p>

                      <div className="mt-3 space-y-3">
                        {selected.red_flags.map((flag, index) => (
                          <div
                            key={`${flag.title}-${index}`}
                            className="rounded-xl border border-white/10 bg-black/20 p-4"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-sm font-semibold text-ink">
                                {flag.title}
                              </p>

                              <span className="font-mono text-[9px] uppercase text-muted-foreground">
                                {flag.severity}
                              </span>
                            </div>

                            <p className="mt-2 text-xs leading-5 text-muted-foreground">
                              {flag.evidence}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {selected.findings.length > 0 && (
                    <div className="mt-5">
                      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                        Findings
                      </p>

                      <div className="mt-3 space-y-3">
                        {selected.findings.map((finding, index) => (
                          <div
                            key={`${finding.claim}-${index}`}
                            className="rounded-xl border border-white/10 bg-black/20 p-4"
                          >
                            <p className="text-sm font-semibold text-ink">
                              {finding.claim}
                            </p>

                            <p className="mt-2 text-xs leading-5 text-muted-foreground">
                              {finding.excerpt}
                            </p>

                            <p className="mt-2 font-mono text-[9px] uppercase text-muted-foreground">
                              {finding.artifact} · {finding.severity}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {selected.email.text && (
                    <details className="mt-5 rounded-xl border border-white/10 bg-black/20">
                      <summary className="cursor-pointer px-4 py-3 font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                        Email body
                      </summary>

                      <pre className="max-h-80 overflow-auto whitespace-pre-wrap border-t border-white/10 p-4 text-xs leading-5 text-muted-foreground">
                        {selected.email.text}
                      </pre>
                    </details>
                  )}
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </main>
  )
}