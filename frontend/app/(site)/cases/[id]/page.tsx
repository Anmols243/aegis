import type { Metadata } from "next"

import { CaseView } from "@/components/aegis/case-view"

export const metadata: Metadata = { title: "Case" }

export default async function CasePage(props: PageProps<"/cases/[id]">) {
  const { id } = await props.params
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10">
      <CaseView id={decodeURIComponent(id)} />
    </div>
  )
}
