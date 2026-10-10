import type { Metadata } from "next"
import { Lock, ScanSearch } from "lucide-react"

import { AnalyzeForm } from "@/components/aegis/analyze-form"
import { PageHero } from "@/components/aegis/page-hero"

export const metadata: Metadata = { title: "Analyze an email" }

export default function AnalyzePage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10">
      <PageHero
        className="mb-6"
        label="Analyze"
        icon={ScanSearch}
        note={
          <>
            <Lock className="size-3" aria-hidden="true" />
            Private to this browser
          </>
        }
        title="Is this email a scam?"
      >
        Paste the message or drop the .eml file. You will watch each agent work, then get a verdict that quotes the exact lines behind it.
      </PageHero>
      <AnalyzeForm />
    </div>
  )
}
