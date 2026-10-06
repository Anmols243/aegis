import type { Metadata } from "next"

import { AnalyzeForm } from "@/components/aegis/analyze-form"

export const metadata: Metadata = { title: "Analyze an email" }

export default function AnalyzePage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 sm:py-14">
      <div className="mb-8 max-w-2xl">
        <p className="label-mono mb-2 text-lime">Analyze</p>
        <h1 className="font-display text-3xl font-bold tracking-tight text-ink sm:text-4xl">Is this email a scam?</h1>
        <p className="mt-3 text-muted-foreground">
          Paste the message or drop the .eml file. You will watch each agent work, then get a verdict that quotes the exact lines behind it.
        </p>
      </div>
      <AnalyzeForm />
    </div>
  )
}
