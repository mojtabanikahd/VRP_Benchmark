import * as LabelPrimitive from "@radix-ui/react-label"
import type { ComponentProps } from "react"

import { cn } from "../../lib/utils"

export function Label({ className, ...props }: ComponentProps<typeof LabelPrimitive.Root>) {
  return (
    <LabelPrimitive.Root
      className={cn("text-[11px] font-medium uppercase tracking-[0.14em] text-ink-soft", className)}
      {...props}
    />
  )
}
