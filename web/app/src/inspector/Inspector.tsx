import type { ReactNode } from "react"
import { zodResolver } from "@hookform/resolvers/zod"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { Button } from "../components/ui/button"
import { Input } from "../components/ui/input"
import { Label } from "../components/ui/label"
import { useStudio } from "../scenario/store"

const nodeSchema = z
  .object({
    x: z.number({ invalid_type_error: "Enter a coordinate" }),
    y: z.number({ invalid_type_error: "Enter a coordinate" }),
    demand: z.number({ invalid_type_error: "Enter a demand" }).int().nonnegative(),
    ready: z.number({ invalid_type_error: "Enter a ready time" }),
    due: z.number({ invalid_type_error: "Enter a due time" }),
    service: z.number({ invalid_type_error: "Enter a service time" }).nonnegative(),
  })
  .refine((value) => value.ready <= value.due, {
    message: "Due time is earlier than ready time",
    path: ["due"],
  })

type NodeForm = z.infer<typeof nodeSchema>

export function Inspector() {
  const node = useStudio((state) => state.nodes.find((item) => item.id === state.selectedId) ?? null)
  const variant = useStudio((state) => state.variant)
  const updateNode = useStudio((state) => state.updateNode)
  const removeSelected = useStudio((state) => state.removeSelected)
  const form = useForm<NodeForm>({
    resolver: zodResolver(nodeSchema),
    values: node
      ? {
          x: node.x,
          y: node.y,
          demand: node.demand,
          ready: node.ready,
          due: node.due,
          service: node.service,
        }
      : { x: 0, y: 0, demand: 0, ready: 0, due: 1000, service: 0 },
  })

  if (!node) {
    return (
      <div className="p-4 text-sm leading-relaxed text-ink-soft">
        Select a depot or customer to edit its demand and, for VRPTW, its time window.
      </div>
    )
  }

  const commit = form.handleSubmit((values) => {
    updateNode(node.id, {
      x: values.x,
      y: values.y,
      demand: node.role === "depot" ? 0 : values.demand,
      ready: values.ready,
      due: values.due,
      service: values.service,
    })
  })

  return (
    <form className="space-y-4 p-4" onBlur={commit}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-ink-soft">{node.role}</p>
          <p className="font-display text-2xl text-ink">{node.role === "depot" ? "Depot" : "Customer"}</p>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={() => removeSelected()}>
          Remove
        </Button>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="X" error={form.formState.errors.x?.message}>
          <Input type="number" step="0.1" {...form.register("x", { valueAsNumber: true })} />
        </Field>
        <Field label="Y" error={form.formState.errors.y?.message}>
          <Input type="number" step="0.1" {...form.register("y", { valueAsNumber: true })} />
        </Field>
      </div>
      {node.role === "customer" ? (
        <Field label="Demand" error={form.formState.errors.demand?.message}>
          <Input type="number" step="1" min="0" {...form.register("demand", { valueAsNumber: true })} />
        </Field>
      ) : null}
      {variant === "VRPTW" ? (
        <div className="grid grid-cols-3 gap-3">
          <Field label="Ready" error={form.formState.errors.ready?.message}>
            <Input type="number" step="1" {...form.register("ready", { valueAsNumber: true })} />
          </Field>
          <Field label="Due" error={form.formState.errors.due?.message}>
            <Input type="number" step="1" {...form.register("due", { valueAsNumber: true })} />
          </Field>
          <Field label="Service" error={form.formState.errors.service?.message}>
            <Input type="number" step="1" min="0" {...form.register("service", { valueAsNumber: true })} />
          </Field>
        </div>
      ) : null}
    </form>
  )
}

function Field({
  label,
  error,
  children,
}: {
  label: string
  error?: string
  children: ReactNode
}) {
  return (
    <label className="block space-y-1.5">
      <Label>{label}</Label>
      {children}
      {error ? <span className="block text-xs text-copper">{error}</span> : null}
    </label>
  )
}
