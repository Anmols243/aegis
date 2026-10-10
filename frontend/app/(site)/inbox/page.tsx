import type { Metadata } from "next"

import { GmailInbox } from "@/components/aegis/gmail-inbox"

export const metadata: Metadata = { title: "Gmail inbox" }

export default function InboxPage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
      <GmailInbox />
    </div>
  )
}
