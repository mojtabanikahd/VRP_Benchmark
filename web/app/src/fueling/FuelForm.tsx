import type { ReactNode } from "react"

import { Button } from "../components/ui/button"
import { Input } from "../components/ui/input"
import { Label } from "../components/ui/label"
import { copy } from "./copy"
import { useFuel, usesTime } from "./store"
import { clockToMinutes, minutesToClock } from "./time"

export function MarkerFields({ id }: { id: string }) {
  const depot = useFuel((state) => state.depots.find((item) => item.id === id) ?? (state.depot?.id === id ? state.depot : null))
  const machine = useFuel((state) => state.machines.find((item) => item.id === id) ?? null)
  const machineTypes = useFuel((state) => state.machineTypes)
  const timed = useFuel((state) => usesTime(state))
  const updateDepot = useFuel((state) => state.updateDepot)
  const updateMachine = useFuel((state) => state.updateMachine)
  const select = useFuel((state) => state.select)
  const removeSelected = useFuel((state) => state.removeSelected)
  const removePoint = () => {
    select(id)
    removeSelected()
  }
  const isDepot = depot?.id === id

  if (isDepot && depot) {
    return (
      <div className="space-y-3" onMouseDown={(event) => event.stopPropagation()}>
        <div className="flex items-start justify-between gap-2">
          <Header eyebrow={copy.depot} title={depot.name} />
          <RemovePoint onRemove={removePoint} />
        </div>
        <Field label={copy.name}>
          <Input value={depot.name} onChange={(event) => updateDepot(depot.id, { name: event.target.value })} />
        </Field>
        {timed ? <div className="grid grid-cols-2 gap-2">
          <Field label={copy.shiftOpens}>
            <Input
              type="time"
              value={minutesToClock(depot.windowOpenMin)}
              onChange={(event) => updateDepot(depot.id, { windowOpenMin: clockToMinutes(event.target.value) })}
            />
          </Field>
          <Field label={copy.shiftCloses}>
            <Input
              type="time"
              value={minutesToClock(depot.windowCloseMin)}
              onChange={(event) => updateDepot(depot.id, { windowCloseMin: clockToMinutes(event.target.value) })}
            />
          </Field>
        </div> : null}
      </div>
    )
  }

  if (!machine) return null
  return (
    <div className="space-y-3" onMouseDown={(event) => event.stopPropagation()}>
      <div className="flex items-start justify-between gap-2">
        <Header eyebrow={copy.machine} title={machine.name} />
        <RemovePoint onRemove={removePoint} />
      </div>
      <Field label={copy.name}>
        <Input value={machine.name} onChange={(event) => updateMachine(id, { name: event.target.value })} />
      </Field>
      <Field label={copy.machineType}>
        <select
          className="h-9 w-full rounded-md border border-line bg-paper px-2 text-sm"
          value={machine.machineTypeId}
          onChange={(event) => {
            const machineTypeId = event.target.value
            const type = machineTypes.find((item) => item.id === machineTypeId)
            updateMachine(id, {
              machineTypeId,
              ...(type ? { fuelL: type.fuelL, durationMin: type.durationMin } : {}),
            })
          }}
        >
          {machineTypes.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </Field>
      <Field label={copy.fuelDemand}>
        <Input
          type="number"
          min={1}
          step={1}
          value={machine.fuelL}
          onChange={(event) => updateMachine(id, { fuelL: Number(event.target.value) })}
        />
      </Field>
      {timed ? (
        <>
          <div className="grid grid-cols-2 gap-2">
            <Field label={copy.windowOpens}>
              <Input
                type="time"
                value={minutesToClock(machine.windowOpenMin)}
                onChange={(event) => updateMachine(id, { windowOpenMin: clockToMinutes(event.target.value) })}
              />
            </Field>
            <Field label={copy.windowCloses}>
              <Input
                type="time"
                value={minutesToClock(machine.windowCloseMin)}
                onChange={(event) => updateMachine(id, { windowCloseMin: clockToMinutes(event.target.value) })}
              />
            </Field>
          </div>
          <Field label={copy.duration}>
            <Input
              type="number"
              min={0}
              step={1}
              value={machine.durationMin}
              onChange={(event) => updateMachine(id, { durationMin: Number(event.target.value) })}
            />
          </Field>
        </>
      ) : null}
    </div>
  )
}

function RemovePoint({ onRemove }: { onRemove: () => void }) {
  return (
    <Button type="button" variant="outline" size="sm" onClick={onRemove}>
      {copy.remove}
    </Button>
  )
}

function Header({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <div>
      <p className="text-[11px] font-medium tracking-[0.14em] text-ink-soft">{eyebrow}</p>
      <p className="font-display text-2xl leading-none text-ink">{title}</p>
    </div>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <Label>{label}</Label>
      {children}
    </label>
  )
}
