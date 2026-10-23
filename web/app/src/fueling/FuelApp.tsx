import { useEffect, useRef } from "react"
import { Panel, PanelGroup, PanelResizeHandle, type ImperativePanelHandle } from "react-resizable-panels"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs"
import { FuelDock } from "./FuelDock"
import { MarkerFields } from "./FuelForm"
import { FuelMap } from "./FuelMap"
import { FuelRail } from "./FuelRail"
import { useFuel } from "./store"

export function FuelApp() {
  const dockRef = useRef<ImperativePanelHandle>(null)
  const solution = useFuel((state) => state.solution)
  const jobError = useFuel((state) => state.jobError)
  const removeSelected = useFuel((state) => state.removeSelected)
  const selectedId = useFuel((state) => state.selectedId)
  const focusPoint = useFuel((state) => state.focusPoint)

  useEffect(() => {
    dockRef.current?.collapse()
  }, [])

  useEffect(() => {
    if (solution || jobError) dockRef.current?.expand()
  }, [jobError, solution])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Delete" && event.key !== "Backspace") return
      const target = event.target
      if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement) {
        return
      }
      removeSelected()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [removeSelected])

  return (
    <PanelGroup direction="vertical" className="h-full">
      <Panel defaultSize={78} minSize={48}>
        <PanelGroup direction="horizontal">
          <Panel defaultSize={24} minSize={18} maxSize={36}>
            <FuelRail />
          </Panel>
          <PanelResizeHandle className="w-px bg-line transition-colors hover:bg-copper/50" />
          <Panel defaultSize={52} minSize={30}>
            <FuelMap />
          </Panel>
          <PanelResizeHandle className="w-px bg-line transition-colors hover:bg-copper/50" />
          <Panel defaultSize={24} minSize={18} maxSize={40}>
            <Tabs defaultValue="details">
              <TabsList>
                <TabsTrigger value="details">Details</TabsTrigger>
                <TabsTrigger value="list">List</TabsTrigger>
              </TabsList>
              <TabsContent value="details">
                {selectedId ? (
                  <div className="p-4">
                    <MarkerFields id={selectedId} />
                  </div>
                ) : (
                  <p className="p-4 text-sm leading-relaxed text-ink-soft">
                    Select a depot or machine to edit its name, fuel demand, and refueling window.
                  </p>
                )}
              </TabsContent>
              <TabsContent value="list">
                <FuelList onSelect={focusPoint} onRemove={removeSelected} />
              </TabsContent>
            </Tabs>
          </Panel>
        </PanelGroup>
      </Panel>
      <PanelResizeHandle className="h-px bg-line transition-colors hover:bg-copper/50" />
      <Panel ref={dockRef} defaultSize={22} minSize={14} collapsible collapsedSize={0}>
        <FuelDock />
      </Panel>
    </PanelGroup>
  )
}

function FuelList({ onSelect, onRemove }: { onSelect: (id: string) => void; onRemove: () => void }) {
  const depot = useFuel((state) => state.depot)
  const machines = useFuel((state) => state.machines)
  const selectedId = useFuel((state) => state.selectedId)
  const select = useFuel((state) => state.select)
  const removeRow = (id: string) => {
    select(id)
    onRemove()
  }
  return (
    <ul className="space-y-1 p-2">
      {depot ? (
        <li>
          <ListButton
            active={selectedId === depot.id}
            onClick={() => onSelect(depot.id)}
            onRemove={() => removeRow(depot.id)}
            label={depot.name}
            meta="Depot"
          />
        </li>
      ) : null}
      {machines.map((machine) => (
        <li key={machine.id}>
          <ListButton
            active={selectedId === machine.id}
            onClick={() => onSelect(machine.id)}
            onRemove={() => removeRow(machine.id)}
            label={machine.name}
            meta={`${machine.fuelL} L`}
          />
        </li>
      ))}
    </ul>
  )
}

function ListButton({
  active,
  onClick,
  onRemove,
  label,
  meta,
}: {
  active: boolean
  onClick: () => void
  onRemove: () => void
  label: string
  meta: string
}) {
  return (
    <div
      className={
        active
          ? "flex w-full items-center gap-2 rounded-md bg-ink px-2 py-1.5 text-sm text-paper"
          : "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-ink/5"
      }
    >
      <button type="button" onClick={onClick} className="flex min-w-0 flex-1 items-baseline justify-between text-left">
        <span className="truncate">{label}</span>
        <span className={active ? "text-paper/70" : "text-ink-soft"}>{meta}</span>
      </button>
      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation()
          onRemove()
        }}
        className={active ? "text-xs text-paper/80 underline" : "text-xs text-ink-soft underline"}
      >
        Remove
      </button>
    </div>
  )
}
