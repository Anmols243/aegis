import type { Metadata } from "next"

import { SignInConfirm } from "@/components/aegis/signin-confirm"

export const metadata: Metadata = { title: "Finish connecting your mailbox" }

export default async function ConnectPage({ searchParams }: { searchParams: Promise<{ [key: string]: string | string[] | undefined }> }) {
  const raw = (await searchParams).state
  const state = typeof raw === "string" ? raw.slice(0, 128) : ""
  return (
    <div className="mx-auto max-w-xl px-4 py-12 sm:px-6 sm:py-16">
      <p className="label-mono mb-2 text-lime">Inbox</p>
      <h1 className="font-display text-3xl font-bold tracking-tight text-ink">Finish connecting your mailbox</h1>
      <SignInConfirm state={state} />
    </div>
  )
}
