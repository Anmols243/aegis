import type { Metadata } from "next"
import Link from "next/link"
import { FolderOpen, Lock, ScanSearch } from "lucide-react"

import { CasesFeed } from "@/components/aegis/cases-feed"
import { HERO_SECONDARY, PageHero } from "@/components/aegis/page-hero"

export const metadata: Metadata = { title: "Cases" }

export default async function CasesPage({ searchParams }: { searchParams: Promise<{ mine?: string | string[] }> }) {
  const { mine } = await searchParams
  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 sm:py-10">
      <PageHero
        className="mb-6"
        label="Cases"
        icon={FolderOpen}
        note={
          <>
            <Lock className="size-3" aria-hidden="true" />
            Yours stay private to this browser
          </>
        }
        title="Cases AEGIS has examined."
        actions={
          <Link href="/analyze" className={HERO_SECONDARY}>
            <ScanSearch className="size-4 text-lime" aria-hidden="true" />
            Analyze an email
          </Link>
        }
      >
        The built-in samples, plus the emails you pasted or sent from this browser. Their email text is deleted after 24 hours, and you can erase
        them any time. Open any case to see the evidence.
      </PageHero>
      <CasesFeed initialMine={mine === "true"} />
    </div>
  )
}
