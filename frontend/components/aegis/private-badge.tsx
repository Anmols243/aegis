import { Lock } from "lucide-react"

import { cn } from "@/lib/utils"

export function PrivateBadge({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-full border border-hair px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground",
        className,
      )}
      title="Private: unlisted, only people with the link can see it"
    >
      <Lock className="size-3" aria-hidden="true" />
      Private
    </span>
  )
}
