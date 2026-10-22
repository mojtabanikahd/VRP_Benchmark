import * as TabsPrimitive from "@radix-ui/react-tabs"
import type { ComponentProps } from "react"

import { cn } from "../../lib/utils"

export function Tabs({ className, ...props }: ComponentProps<typeof TabsPrimitive.Root>) {
  return <TabsPrimitive.Root className={cn("flex h-full min-h-0 flex-col", className)} {...props} />
}

export function TabsList({ className, ...props }: ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn("grid grid-cols-2 gap-1 border-b border-line p-2", className)}
      {...props}
    />
  )
}

export function TabsTrigger({ className, ...props }: ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "rounded-md px-2 py-1.5 text-sm text-ink-soft data-[state=active]:bg-ink data-[state=active]:text-paper",
        className,
      )}
      {...props}
    />
  )
}

export function TabsContent({ className, ...props }: ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content className={cn("min-h-0 flex-1 overflow-auto outline-none", className)} {...props} />
  )
}
