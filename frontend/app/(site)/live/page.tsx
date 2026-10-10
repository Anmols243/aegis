import type { Metadata } from "next"

import { LiveInboxView } from "@/components/aegis/live-inbox"

export const metadata: Metadata = { title: "Test the system" }

export default function LivePage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
      <LiveInboxView />
    </div>
  )
}
