import type { Metadata } from "next"

import { ShareView } from "@/components/aegis/share-view"

export const metadata: Metadata = { title: "Shared verdict", robots: { index: false, follow: false } }

export default async function SharePage(props: PageProps<"/share/[token]">) {
  const { token } = await props.params
  return <ShareView token={decodeURIComponent(token)} />
}
