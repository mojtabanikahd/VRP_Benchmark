import { useEffect, useRef, type ReactNode } from "react"

import { Button } from "../components/ui/button"
import { Input } from "../components/ui/input"
import { Label } from "../components/ui/label"
import { useFuel } from "./store"
import { clockToMinutes, minutesToClock } from "./time"

let holdMapClicksUntil = 0

export function mapClickHeld() {
  return performance.now() < holdMapClicksUntil
}

function holdMapClicks() {
  holdMapClicksUntil = performance.now() + 300
}

export function MarkerFields({ id }: { id: string }) {
  const depot = useFuel((state) => state.depot)
  const machine = useFuel((state) => state.machines.find((item) => item.id === id) ?? null)
  const machineTypes = useFuel((state) => state.machineTypes)
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
          <Header eyebrow="Depot" title={depot.name} />
          <RemovePoint onRemove={removePoint} />
        </div>
        <Field label="Name">
          <Input value={depot.name} onChange={(event) => updateDepot({ name: event.target.value })} />
        </Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Shift opens">
            <Input
              type="time"
              value={minutesToClock(depot.windowOpenMin)}
              onChange={(event) => updateDepot({ windowOpenMin: clockToMinutes(event.target.value) })}
            />
          </Field>
          <Field label="Shift closes">
            <Input
              type="time"
              value={minutesToClock(depot.windowCloseMin)}
              onChange={(event) => updateDepot({ windowCloseMin: clockToMinutes(event.target.value) })}
            />
          </Field>
        </div>
      </div>
    )
  }

  if (!machine) return null
  return (
    <div className="space-y-3" onMouseDown={(event) => event.stopPropagation()}>
      <div className="flex items-start justify-between gap-2">
        <Header eyebrow="Machine" title={machine.name} />
        <RemovePoint onRemove={removePoint} />
      </div>
      <Field label="Name">
        <Input value={machine.name} onChange={(event) => updateMachine(id, { name: event.target.value })} />
      </Field>
      <Field label="Machine type">
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
      <Field label="Fuel demand (L)">
        <Input
          type="number"
          min={1}
          step={1}
          value={machine.fuelL}
          onChange={(event) => updateMachine(id, { fuelL: Number(event.target.value) })}
        />
      </Field>
      <div className="grid grid-cols-2 gap-2">
        <Field label="Window opens">
          <Input
            type="time"
            value={minutesToClock(machine.windowOpenMin)}
            onChange={(event) => updateMachine(id, { windowOpenMin: clockToMinutes(event.target.value) })}
          />
        </Field>
        <Field label="Window closes">
          <Input
            type="time"
            value={minutesToClock(machine.windowCloseMin)}
            onChange={(event) => updateMachine(id, { windowCloseMin: clockToMinutes(event.target.value) })}
          />
        </Field>
      </div>
      <Field label="Refueling duration (min)">
        <Input
          type="number"
          min={0}
          step={1}
          value={machine.durationMin}
          onChange={(event) => updateMachine(id, { durationMin: Number(event.target.value) })}
        />
      </Field>
    </div>
  )
}

function RemovePoint({ onRemove }: { onRemove: () => void }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const node = ref.current
    if (!node) return
    const stop = (event: Event) => {
      event.preventDefault()
      event.stopPropagation()
    }
    const onClick = (event: Event) => {
      stop(event)
      holdMapClicks()
      onRemove()
    }
    node.addEventListener("click", onClick, true)
    node.addEventListener("mousedown", stop, true)
    node.addEventListener("mouseup", stop, true)
    node.addEventListener("pointerdown", stop, true)
    node.addEventListener("pointerup", stop, true)
    return () => {
      node.removeEventListener("click", onClick, true)
      node.removeEventListener("mousedown", stop, true)
      node.removeEventListener("mouseup", stop, true)
      node.removeEventListener("pointerdown", stop, true)
      node.removeEventListener("pointerup", stop, true)
    }
  }, [onRemove])
  return (
    <div ref={ref}>
      <Button type="button" variant="outline" size="sm">
        Remove
      </Button>
    </div>
  )
}

function Header({ eyebrow, title }: { eyebrow: string; title: string }) {
  return (
    <div>
      <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-ink-soft">{eyebrow}</p>
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
