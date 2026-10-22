import type { InputHTMLAttributes } from "react"

import { cn } from "../../lib/utils"

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-9 w-full rounded-md border border-line bg-paper px-2.5 text-sm text-ink outline-none transition-colors placeholder:text-ink-soft/60 focus:border-copper/60 focus:ring-2 focus:ring-copper/20",
        className,
      )}
      {...props}
    />
  )
}
