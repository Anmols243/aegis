"use client"

import * as React from "react"
import Link from "next/link"
import { Share2 } from "lucide-react"

import { ErrorState, LoadingState } from "@/components/aegis/bits"
import { PageHero } from "@/components/aegis/page-hero"
import { VerdictReport } from "@/components/aegis/verdict-report"
import { api, ApiError, type Analysis } from "@/lib/api"

export function ShareView({ token }: { token: string }) {
  const [a, setA] = React.useState<Analysis | null>(null)
  const [err, setErr] = React.useState<string | null>(null)

  React.useEffect(() => {
    api
      .share(token)
      .then(setA)
      .catch((e: unknown) =>
        setErr(e instanceof ApiError && e.status === 404 ? "This share link is not valid or has been removed." : "Could not load this verdict right now."),
      )
  }, [token])

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 sm:py-12">
      <header className="mb-8 flex flex-wrap items-center justify-between gap-3">
        <Link href="/" className="font-display text-2xl font-extrabold tracking-tight text-ink">
          AEGIS<span className="text-lime">.</span>
        </Link>
      </header>
      {err ? (
        <ErrorState message={err} />
      ) : !a ? (
        <LoadingState label="Loading verdict" />
      ) : (
        <>
          <PageHero className="mb-6" label="Shared verdict" icon={Share2} title={a.subject || a.email?.subject || "(no subject)"} accent={false} beam={false}>
            Someone checked this email with AEGIS and wanted you to see the result.
            {a.sender || a.email?.from ? <span className="mt-1 block break-words font-mono text-xs">from {a.sender || a.email?.from}</span> : null}
          </PageHero>
          <VerdictReport analysis={a} mode="share" />
          <p className="mt-10 text-center text-sm text-muted-foreground">
            Got a suspicious email of your own?{" "}
            <Link href="/analyze" className="font-medium text-lime hover:underline">
              Check it with AEGIS
            </Link>
          </p>
        </>
      )}
    </div>
  )
}
