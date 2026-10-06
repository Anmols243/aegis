"use client"

import * as React from "react"
import { motion, useReducedMotion } from "motion/react"

import { cn } from "@/lib/utils"

export interface BorderBeamProps extends React.ComponentProps<"div"> {
  /** Length of the light streak in CSS pixels. */
  size?: number
  /** Seconds for one full lap around the border. */
  duration?: number
  /** Start offset in seconds, so neighbouring beams do not move in lockstep. */
  delay?: number
  /** Streak head color. */
  colorFrom?: string
  /** Streak tail color. */
  colorTo?: string
  /** Border ring thickness in CSS pixels. */
  borderWidth?: number
  /** Corner radius the streak follows, in CSS pixels (match the wrapper's rounded class). */
  radius?: number
}

/**
 * BorderBeam: wraps its children and sends a short lime streak around the
 * border at constant speed. The streak rides `offset-path: rect(... round r)`
 * so it keeps the same pace along long and short edges, and is masked to a
 * thin ring so it only ever lights the border. Hidden under reduced motion.
 */
export function BorderBeam({
  size = 90,
  duration = 7,
  delay = 0,
  colorFrom = "#d9ff3d",
  colorTo = "#ffffff",
  borderWidth = 1,
  radius = 20,
  className,
  children,
  ...rest
}: BorderBeamProps) {
  const reduce = useReducedMotion()
  return (
    <div data-slot="border-beam" className={cn("relative", className)} {...rest}>
      {children}
      {!reduce && (
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 z-[2] overflow-hidden rounded-[inherit]"
          style={{
            padding: borderWidth,
            WebkitMask: "linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0)",
            WebkitMaskComposite: "xor",
            maskComposite: "exclude",
          }}
        >
          <motion.div
            className="absolute aspect-square"
            style={{
              width: size,
              offsetPath: `rect(0 auto auto 0 round ${radius}px)`,
              offsetAnchor: "50% 50%",
              background: `linear-gradient(to left, ${colorTo}, ${colorFrom}, transparent)`,
            }}
            initial={{ offsetDistance: "0%" }}
            animate={{ offsetDistance: ["0%", "100%"] }}
            transition={{ repeat: Infinity, ease: "linear", duration, delay: -delay }}
          />
        </div>
      )}
    </div>
  )
}

export default BorderBeam
