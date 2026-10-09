import type { Metadata } from "next"

import { CasesFeed } from "@/components/aegis/cases-feed"

export const metadata: Metadata = { title: "Cases" }

export default async function CasesPage({ searchParams }: { searchParams: Promise<{ mine?: string | string[] }> }) {
  const { mine } = await searchParams
  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-14">
      <div className="mb-7">
        <p className="label-mono mb-2 text-lime">Cases</p>
        <h1 className="font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">Cases AEGIS has examined.</h1>
        <p className="mt-3 text-muted-foreground">
          The built-in samples, plus the emails you pasted or sent from this browser. Yours are visible to this browser only, deleted after 24
          hours, and you can erase them any time. Open any case to see the evidence.
        </p>
      </div>
      <CasesFeed initialMine={mine === "true"} />
    </div>
  )
}
