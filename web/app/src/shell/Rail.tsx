import { Upload } from "lucide-react"
import { useRef } from "react"

import { uploadInstance } from "../lib/api"
import { useStudio } from "../scenario/store"
import { scenarioIssues } from "../scenario/issues"
import { Button } from "../components/ui/button"
import { Input } from "../components/ui/input"
import { Label } from "../components/ui/label"
import { Slider } from "../components/ui/slider"
import { VariantToggle } from "../components/ui/variant-toggle"
import { SolverPicker } from "./SolverPicker"
import { useSolve } from "../session/useSolve"

export function Rail() {
  const name = useStudio((state) => state.name)
  const variant = useStudio((state) => state.variant)
  const capacity = useStudio((state) => state.capacity)
  const timeBudgetS = useStudio((state) => state.timeBudgetS)
  const seed = useStudio((state) => state.seed)
  const solver = useStudio((state) => state.solver)
  const uploadError = useStudio((state) => state.uploadError)
  const setName = useStudio((state) => state.setName)
  const setVariant = useStudio((state) => state.setVariant)
  const setCapacity = useStudio((state) => state.setCapacity)
  const setTimeBudget = useStudio((state) => state.setTimeBudget)
  const setSeed = useStudio((state) => state.setSeed)
  const addDepot = useStudio((state) => state.addDepot)
  const loadPreview = useStudio((state) => state.loadPreview)
  const setUploadError = useStudio((state) => state.setUploadError)
  const nodes = useStudio((state) => state.nodes)
  const issues = scenarioIssues({ variant, capacity, nodes })
  const fileRef = useRef<HTMLInputElement>(null)
  const { solve, running, error } = useSolve()
  const blocked = issues.length > 0 || !solver

  return (
    <div className="flex h-full min-h-0 flex-col bg-paper">
      <header className="border-b border-line px-4 py-4">
        <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-copper">Dispatch</p>
        <h1 className="font-display text-3xl leading-none text-ink">VRP Studio</h1>
      </header>
      <div className="min-h-0 flex-1 space-y-5 overflow-auto px-4 py-4">
        <section className="space-y-2">
          <Label htmlFor="scenario-name">Scenario</Label>
          <Input id="scenario-name" value={name} onChange={(event) => setName(event.target.value)} />
        </section>
        <section className="space-y-2">
          <Label>Variant</Label>
          <VariantToggle value={variant} onChange={setVariant} />
        </section>
        <section className="space-y-2">
          <Label>Solver</Label>
          <SolverPicker />
        </section>
        <section className="space-y-2">
          <Label htmlFor="capacity">Capacity</Label>
          <Input
            id="capacity"
            type="number"
            min={1}
            value={capacity}
            onChange={(event) => setCapacity(Number(event.target.value))}
          />
          {variant === "MDVRP" ? (
            <Button type="button" variant="outline" className="w-full" onClick={() => addDepot()}>
              Add depot
            </Button>
          ) : null}
        </section>
        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <Label>Time budget</Label>
            <span className="text-sm tabular-nums text-ink">{timeBudgetS}s</span>
          </div>
          <Slider value={timeBudgetS} min={1} max={60} step={1} onValueChange={setTimeBudget} />
          <Label htmlFor="seed">Seed</Label>
          <Input
            id="seed"
            type="number"
            min={0}
            value={seed}
            onChange={(event) => setSeed(Number(event.target.value))}
          />
        </section>
        <section>
          <input
            ref={fileRef}
            type="file"
            className="hidden"
            accept=".vrp,.txt"
            onChange={(event) => {
              const file = event.target.files?.[0]
              event.target.value = ""
              if (!file) return
              void uploadInstance(variant, file)
                .then(loadPreview)
                .catch((reason: unknown) => {
                  setUploadError(reason instanceof Error ? reason.message : "Upload failed")
                })
            }}
          />
          <Button type="button" variant="outline" className="w-full" onClick={() => fileRef.current?.click()}>
            <Upload className="size-4" />
            Load instance
          </Button>
          {uploadError ? <p className="mt-2 text-xs leading-relaxed text-copper">{uploadError}</p> : null}
        </section>
        {issues.length > 0 ? (
          <ul className="space-y-1 text-xs leading-relaxed text-copper">
            {issues.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        ) : null}
      </div>
      <div className="border-t border-line p-4">
        {error ? <p className="mb-2 text-xs leading-relaxed text-copper">{error}</p> : null}
        <Button type="button" size="lg" className="w-full" disabled={blocked || running} onClick={() => solve()}>
          {running ? "Solving" : "Solve"}
        </Button>
      </div>
    </div>
  )
}
