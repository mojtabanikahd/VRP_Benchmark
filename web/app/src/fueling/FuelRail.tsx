import { useQuery } from "@tanstack/react-query"
import { Download, Upload } from "lucide-react"
import { useEffect, useRef, type ReactNode } from "react"

import { Button } from "../components/ui/button"
import { Input } from "../components/ui/input"
import { Label } from "../components/ui/label"
import { Slider } from "../components/ui/slider"
import { cn } from "../lib/utils"
import { VariantToggle } from "../components/ui/variant-toggle"
import { fetchFuelCatalog } from "./api"
import { copy } from "./copy"
import { downloadScenario, parseScenarioText } from "./file"
import { readImageFile } from "./icons"
import { fuelIssues } from "./issues"
import { useFuel, usesManyDepots, usesTime } from "./store"
import { useFuelSolve } from "./useFuelSolve"

export function FuelRail() {
  const profile = useFuel((state) => state.profile)
  const variant = useFuel((state) => state.variant)
  const timed = useFuel((state) => usesTime(state))
  const manyDepots = useFuel((state) => usesManyDepots(state))
  const name = useFuel((state) => state.name)
  const machineTypes = useFuel((state) => state.machineTypes)
  const tanker = useFuel((state) => state.tanker)
  const depot = useFuel((state) => state.depot)
  const depots = useFuel((state) => state.depots)
  const machines = useFuel((state) => state.machines)
  const solver = useFuel((state) => state.solver)
  const timeBudgetS = useFuel((state) => state.timeBudgetS)
  const seed = useFuel((state) => state.seed)
  const fileError = useFuel((state) => state.fileError)
  const canUndo = useFuel((state) => state.canUndo)
  const canRedo = useFuel((state) => state.canRedo)
  const setName = useFuel((state) => state.setName)
  const setVariant = useFuel((state) => state.setVariant)
  const setSolver = useFuel((state) => state.setSolver)
  const ensureSolver = useFuel((state) => state.ensureSolver)
  const undo = useFuel((state) => state.undo)
  const redo = useFuel((state) => state.redo)
  const reset = useFuel((state) => state.reset)
  const setTimeBudget = useFuel((state) => state.setTimeBudget)
  const setSeed = useFuel((state) => state.setSeed)
  const addMachineType = useFuel((state) => state.addMachineType)
  const updateMachineType = useFuel((state) => state.updateMachineType)
  const removeMachineType = useFuel((state) => state.removeMachineType)
  const updateTanker = useFuel((state) => state.updateTanker)
  const loadFile = useFuel((state) => state.loadFile)
  const setFileError = useFuel((state) => state.setFileError)
  const fileRef = useRef<HTMLInputElement>(null)
  const catalogVariant = profile === "studio" ? variant : "VRPTW"
  const catalog = useQuery({
    queryKey: ["fuel-catalog", catalogVariant],
    queryFn: () => fetchFuelCatalog(catalogVariant),
  })
  const { solve, running } = useFuelSolve()
  const issues = fuelIssues({ depot, depots, machines, machineTypes, tanker, solver, timed, manyDepots })

  const solverNames = catalog.data?.solvers.map((item) => item.name).join("\n") ?? ""
  useEffect(() => {
    const names = solverNames.split("\n").filter(Boolean)
    const first = names[0]
    if (!first) return
    if (!solver || !names.includes(solver)) ensureSolver(first)
  }, [ensureSolver, solver, solverNames])

  return (
    <div className="flex h-full min-h-0 flex-col bg-paper">
      <header className="border-b border-line px-4 py-4">
        <p className="text-[11px] font-medium tracking-[0.18em] text-copper">
          {profile === "studio" ? copy.studioEyebrow : copy.eyebrow}
        </p>
        <h1 className="font-display text-3xl leading-none text-ink">
          {profile === "studio" ? copy.studioTitle : copy.appTitle}
        </h1>
      </header>
      <div className="min-h-0 flex-1 space-y-5 overflow-auto px-4 py-4">
        <section className="space-y-2">
          <Label htmlFor="fuel-name">{copy.scenario}</Label>
          <Input id="fuel-name" value={name} onChange={(event) => setName(event.target.value)} />
        </section>
        {profile === "studio" ? (
          <section className="space-y-2">
            <Label>{copy.variant}</Label>
            <VariantToggle value={variant} onChange={setVariant} />
          </section>
        ) : null}
        <TypeSection
          title={copy.machineTypes}
          onAdd={addMachineType}
          addLabel={copy.addMachineType}
        >
          {machineTypes.map((item) => (
            <TypeRow
              key={item.id}
              name={item.name}
              image={item.image}
              fuelL={item.fuelL}
              durationMin={item.durationMin}
              onName={(value) => updateMachineType(item.id, { name: value })}
              onFuel={(value) => updateMachineType(item.id, { fuelL: wholeLiters(value) })}
              onDuration={timed ? (value) => updateMachineType(item.id, { durationMin: minutes(value) }) : undefined}
              onImage={(image) => updateMachineType(item.id, { image })}
              onRemove={machineTypes.length > 1 ? () => removeMachineType(item.id) : undefined}
              onImageError={setFileError}
            />
          ))}
        </TypeSection>
        <section className="space-y-2">
          <Label>{copy.tanker}</Label>
          <TypeRow
            name={tanker.name}
            image={tanker.image}
            capacityL={tanker.capacityL}
            onName={(value) => updateTanker({ name: value })}
            onCapacity={(value) => updateTanker({ capacityL: Math.max(1, Math.round(value)) })}
            onImage={(image) => updateTanker({ image })}
            onImageError={setFileError}
          />
        </section>
        <section className="space-y-2">
          <Label>{copy.solver}</Label>
          {catalog.isLoading ? <p className="text-sm text-ink-soft">{copy.loadingSolvers}</p> : null}
          {catalog.isError ? <p className="text-sm text-copper">{copy.catalogUnavailable}</p> : null}
          <div className="space-y-1.5">
            {catalog.data?.solvers.map((item) => {
              const active = item.name === solver
              return (
                <button
                  key={item.name}
                  type="button"
                  onClick={() => setSolver(item.name)}
                  className={cn(
                    "flex w-full items-baseline justify-between rounded-md border px-2.5 py-2 text-start",
                    active ? "border-ink bg-ink text-paper" : "border-line bg-paper hover:border-ink/30",
                  )}
                >
                  <span className="text-sm font-medium">{item.name === "pyvrp" ? "PyVRP" : "OR-Tools"}</span>
                  <span className={cn("text-[11px]", active ? "text-paper/70" : "text-ink-soft")}>{item.version}</span>
                </button>
              )
            })}
          </div>
        </section>
        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <Label>{copy.timeBudget}</Label>
            <span className="text-sm tabular-nums text-ink">{timeBudgetS}s</span>
          </div>
          <Slider value={timeBudgetS} min={1} max={60} step={1} onValueChange={setTimeBudget} />
          <Label htmlFor="fuel-seed">{copy.seed}</Label>
          <Input
            id="fuel-seed"
            type="number"
            min={0}
            value={seed}
            onChange={(event) => setSeed(Number(event.target.value))}
          />
        </section>
        <section className="grid grid-cols-2 gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() =>
              downloadScenario({
                profile,
                variant,
                name,
                machineTypes,
                tanker,
                depot,
                depots,
                machines,
                solver,
                timeBudgetS,
                seed,
              })
            }
          >
            <Download className="size-4" />
            {copy.save}
          </Button>
          <Button type="button" variant="outline" onClick={() => fileRef.current?.click()}>
            <Upload className="size-4" />
            {copy.load}
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0]
              event.target.value = ""
              if (!file) return
              void file
                .text()
                .then((text) => parseScenarioText(text, profile))
                .then(loadFile)
                .catch((reason: unknown) => {
                  setFileError(reason instanceof Error ? reason.message : copy.loadFailed)
                })
            }}
          />
        </section>
        <section className="grid grid-cols-2 gap-2">
          <Button type="button" variant="outline" disabled={!canUndo} onClick={undo}>
            {copy.undo}
          </Button>
          <Button type="button" variant="outline" disabled={!canRedo} onClick={redo}>
            {copy.redo}
          </Button>
          <Button type="button" variant="outline" className="col-span-2" onClick={reset}>
            {copy.reset}
          </Button>
        </section>
        {fileError ? <p className="text-xs leading-relaxed text-copper">{fileError}</p> : null}
        {issues.length > 0 ? (
          <ul className="space-y-1 text-xs leading-relaxed text-copper">
            {issues.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        ) : null}
      </div>
      <div className="border-t border-line p-4">
        <Button type="button" size="lg" className="w-full" disabled={issues.length > 0 || running} onClick={() => solve()}>
          {running ? copy.solving : copy.solve}
        </Button>
      </div>
    </div>
  )
}

function TypeSection({
  title,
  addLabel,
  onAdd,
  children,
}: {
  title: string
  addLabel: string
  onAdd: () => void
  children: ReactNode
}) {
  return (
    <section className="space-y-2">
      <Label>{title}</Label>
      <div className="space-y-2">{children}</div>
      <Button type="button" variant="outline" className="w-full" onClick={onAdd}>
        {addLabel}
      </Button>
    </section>
  )
}

function wholeLiters(value: number) {
  if (!Number.isFinite(value)) return 1
  return Math.max(1, Math.round(value))
}

function minutes(value: number) {
  if (!Number.isFinite(value)) return 0
  return Math.max(0, value)
}

function TypeRow({
  name,
  image,
  active,
  capacityL,
  fuelL,
  durationMin,
  onSelect,
  onName,
  onCapacity,
  onFuel,
  onDuration,
  onImage,
  onRemove,
  onImageError,
}: {
  name: string
  image: string
  active?: boolean
  capacityL?: number
  fuelL?: number
  durationMin?: number
  onSelect?: () => void
  onName: (value: string) => void
  onCapacity?: (value: number) => void
  onFuel?: (value: number) => void
  onDuration?: (value: number) => void
  onImage: (image: string) => void
  onRemove?: () => void
  onImageError: (message: string) => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  return (
    <div className={cn("space-y-2 rounded-md border p-2", active ? "border-ink" : "border-line")}>
      <div className="flex items-center gap-2">
        <button type="button" onClick={() => inputRef.current?.click()} title={copy.replaceImage}>
          <img src={image} alt="" className="size-9 rounded-md object-cover" />
        </button>
        <Input value={name} onChange={(event) => onName(event.target.value)} />
        {onSelect ? (
          <Button type="button" variant={active ? "default" : "outline"} size="sm" onClick={onSelect}>
            {copy.select}
          </Button>
        ) : null}
      </div>
      {onCapacity ? (
        <label className="block space-y-1">
          <Label>{copy.tankCapacity}</Label>
          <Input
            type="number"
            min={1}
            step={1}
            value={capacityL}
            onChange={(event) => onCapacity(Number(event.target.value))}
          />
        </label>
      ) : null}
      {onFuel ? (
        <label className="block space-y-1">
          <Label>{copy.defaultFuel}</Label>
          <Input
            type="number"
            min={1}
            step={1}
            value={fuelL}
            onChange={(event) => onFuel(Number(event.target.value))}
          />
        </label>
      ) : null}
      {onDuration ? (
        <label className="block space-y-1">
          <Label>{copy.defaultDuration}</Label>
          <Input
            type="number"
            min={0}
            step={1}
            value={durationMin}
            onChange={(event) => onDuration(Number(event.target.value))}
          />
        </label>
      ) : null}
      {onRemove ? (
        <button type="button" className="text-xs text-ink-soft underline" onClick={onRemove}>
          {copy.removeType}
        </button>
      ) : null}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0]
          event.target.value = ""
          if (!file) return
          void readImageFile(file).then(onImage).catch((reason: unknown) => {
            onImageError(reason instanceof Error ? reason.message : copy.imageRead)
          })
        }}
      />
    </div>
  )
}
