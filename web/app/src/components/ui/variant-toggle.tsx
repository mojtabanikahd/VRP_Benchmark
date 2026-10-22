import * as ToggleGroupPrimitive from "@radix-ui/react-toggle-group"

import { VARIANTS, type Variant } from "../../scenario/types"

export function VariantToggle({
  value,
  onChange,
}: {
  value: Variant
  onChange: (variant: Variant) => void
}) {
  return (
    <ToggleGroupPrimitive.Root
      type="single"
      value={value}
      onValueChange={(next) => {
        if (next === "CVRP" || next === "VRPTW" || next === "MDVRP") onChange(next)
      }}
      className="grid grid-cols-3 gap-1 rounded-lg bg-ink/6 p-1"
      aria-label="Problem variant"
    >
      {VARIANTS.map((variant) => (
        <ToggleGroupPrimitive.Item
          key={variant}
          value={variant}
          className="rounded-md px-1 py-1.5 text-xs font-medium tracking-wide text-ink-soft transition-colors data-[state=on]:bg-paper data-[state=on]:text-ink data-[state=on]:shadow-sm"
        >
          {variant}
        </ToggleGroupPrimitive.Item>
      ))}
    </ToggleGroupPrimitive.Root>
  )
}
