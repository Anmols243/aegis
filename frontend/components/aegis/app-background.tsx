"use client"

import * as React from "react"
import { SonarGrid } from "@/components/ui/sonar-grid"

// Elements whose clicks belong to the UI, not to the background ping.
const INTERACTIVE = "a, button, input, textarea, select, label, summary, [role=button], [role=tab], [data-no-ping], .hud"

/**
 * App-wide sonar background. The grid sits in a fixed layer behind the page;
 * clicks on empty space are re-dispatched to it so it can answer with a ping,
 * while clicks on controls and panels are left alone.
 */
export function AppBackground() {
  const hostRef = React.useRef<HTMLDivElement | null>(null)

  React.useEffect(() => {
    const onDown = (e: PointerEvent) => {
      const host = hostRef.current
      if (!host || !e.isTrusted) return
      const target = e.target as Element | null
      if (target && target.closest && target.closest(INTERACTIVE)) return
      host.dispatchEvent(new PointerEvent("pointerdown", { clientX: e.clientX, clientY: e.clientY }))
    }
    document.addEventListener("pointerdown", onDown)
    return () => document.removeEventListener("pointerdown", onDown)
  }, [])

  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10">
      <SonarGrid ref={hostRef} className="h-full w-full" baseOpacity={0.16} interactive />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_70%_55%_at_50%_35%,transparent_0%,rgba(10,12,14,0.55)_70%,rgba(10,12,14,0.85)_100%)]" />
    </div>
  )
}
