import type { ReactNode } from "react"

import { cn } from "../../lib/utils"

export function Badge({
  className,
  tone = "neutral",
  children,
}: {
  className?: string
  tone?: "neutral" | "ok" | "bad"
  children: ReactNode
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
        tone === "neutral" && "bg-ink/8 text-ink-soft",
        tone === "ok" && "bg-emerald-700/10 text-emerald-800",
        tone === "bad" && "bg-copper/10 text-copper",
        className,
      )}
    >
      {children}
    </span>
  )
}
