import type { Metadata } from "next"

import { CasesFeed } from "@/components/aegis/cases-feed"

export const metadata: Metadata = { title: "Cases" }

export default function CasesPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
      <div className="mb-7">
        <p className="label-mono mb-2 text-lime">Cases</p>
        <h1 className="font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">Every email AEGIS has examined.</h1>
        <p className="mt-3 text-muted-foreground">From the web, the forwarding inbox and the red team. Open any case to see the evidence.</p>
      </div>
      <CasesFeed />
    </div>
  )
}
