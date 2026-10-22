import { useQuery } from "@tanstack/react-query"
import { useEffect } from "react"

import { fetchCatalog } from "../lib/api"
import { cn } from "../lib/utils"
import { useStudio } from "../scenario/store"

export function SolverPicker() {
  const variant = useStudio((state) => state.variant)
  const solver = useStudio((state) => state.solver)
  const setSolver = useStudio((state) => state.setSolver)
  const catalog = useQuery({ queryKey: ["catalog"], queryFn: fetchCatalog })

  const options = catalog.data?.variants.find((item) => item.variant === variant)?.solvers ?? []

  const solverName = options[0]?.name
  useEffect(() => {
    if (!solverName) return
    if (!solver || !options.some((item) => item.name === solver)) {
      setSolver(solverName)
    }
  }, [options, setSolver, solver, solverName])

  if (catalog.isLoading) {
    return <p className="text-sm text-ink-soft">Loading solvers…</p>
  }
  if (catalog.isError) {
    return <p className="text-sm text-copper">The solver catalog is unavailable. Start the API and refresh.</p>
  }

  return (
    <div className="space-y-1.5" role="listbox" aria-label={`${variant} solvers`}>
      {options.map((item) => {
        const active = item.name === solver
        return (
          <button
            key={item.name}
            type="button"
            role="option"
            aria-selected={active}
            onClick={() => setSolver(item.name)}
            className={cn(
              "flex w-full items-baseline justify-between rounded-md border px-2.5 py-2 text-left transition-colors",
              active ? "border-ink bg-ink text-paper" : "border-line bg-paper hover:border-ink/30",
            )}
          >
            <span className="text-sm font-medium">{labelFor(item.name)}</span>
            <span className={cn("text-[11px]", active ? "text-paper/70" : "text-ink-soft")}>{item.version}</span>
          </button>
        )
      })}
    </div>
  )
}

function labelFor(name: string) {
  if (name === "pyvrp") return "PyVRP"
  if (name === "ortools") return "OR-Tools"
  if (name === "vroom") return "VROOM"
  if (name === "vrpsolvereasy") return "VRPSolverEasy"
  return name
}
