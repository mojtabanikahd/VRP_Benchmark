import * as SliderPrimitive from "@radix-ui/react-slider"

import { cn } from "../../lib/utils"

export function Slider({
  className,
  value,
  onValueChange,
  min,
  max,
  step,
}: {
  className?: string
  value: number
  min: number
  max: number
  step: number
  onValueChange: (value: number) => void
}) {
  return (
    <SliderPrimitive.Root
      className={cn("relative flex h-5 w-full touch-none items-center", className)}
      value={[value]}
      min={min}
      max={max}
      step={step}
      onValueChange={(next) => onValueChange(next[0] ?? value)}
    >
      <SliderPrimitive.Track className="relative h-1 grow rounded-full bg-ink/10">
        <SliderPrimitive.Range className="absolute h-full rounded-full bg-copper" />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb className="block size-3.5 rounded-full border border-copper bg-paper shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-copper/40" />
    </SliderPrimitive.Root>
  )
}
