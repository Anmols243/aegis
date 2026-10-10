import type { Metadata } from "next"
import { Mail } from "lucide-react"

import { PageHero } from "@/components/aegis/page-hero"
import { SignInConfirm } from "@/components/aegis/signin-confirm"

export const metadata: Metadata = { title: "Finish connecting your mailbox" }

// The sign-in callback lands here when Google returned to a different browser than the one
// that started it; the mailbox is attached only after this person confirms the code.
export default async function ConnectPage({ searchParams }: { searchParams: Promise<{ [key: string]: string | string[] | undefined }> }) {
  const raw = (await searchParams).state
  const state = typeof raw === "string" ? raw.slice(0, 128) : ""
  return (
    <div className="mx-auto max-w-xl px-4 py-8 sm:px-6 sm:py-10">
      <PageHero label="Inbox" icon={Mail} title="Finish connecting your mailbox" beam={false} />
      <SignInConfirm state={state} />
    </div>
  )
}
