import { motion } from "motion/react"

import { Badge } from "../components/ui/badge"
import { ROUTE_COLORS, SELECTED_ROUTE } from "../scenario/types"
import { useFuel } from "./store"

export function FuelDock() {
  const solution = useFuel((state) => state.solution)
  const jobError = useFuel((state) => state.jobError)
  const depot = useFuel((state) => state.depot)
  const machines = useFuel((state) => state.machines)
  const selectedRoute = useFuel((state) => state.selectedRoute)
  const selectRoute = useFuel((state) => state.selectRoute)

  if (jobError) {
    return (
      <div className="flex h-full items-center px-6">
        <p className="text-sm text-copper">{jobError}</p>
      </div>
    )
  }

  if (!solution) {
    return (
      <div className="flex h-full items-center px-6 text-sm text-ink-soft">
        Solved tanker routes appear here, drawn on the streets they drive.
      </div>
    )
  }

  return (
    <motion.div
      className="grid h-full grid-cols-[220px_minmax(0,1fr)] gap-6 px-6 py-4"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
    >
      <div>
        <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-ink-soft">Driving distance</p>
        <p className="font-display text-5xl leading-none text-ink">{formatKm(solution.objective)}</p>
        <p className="mt-1 text-xs text-ink-soft">kilometers</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Badge tone={solution.feasible ? "ok" : "bad"}>{solution.feasible ? "Feasible" : "Infeasible"}</Badge>
          <Badge>{solution.num_vehicles} tankers</Badge>
          <Badge>{solution.runtime_s.toFixed(2)}s</Badge>
        </div>
      </div>
      <div className="min-h-0 overflow-auto">
        {solution.violations.length > 0 ? (
          <ul className="mb-3 space-y-1 text-sm text-copper">
            {solution.violations.map((violation) => (
              <li key={violation}>{violation}</li>
            ))}
          </ul>
        ) : null}
        <ul className="space-y-2">
          {solution.routes.map((route, index) => {
            if (route.length === 0) return null
            const path = solution.paths[index]
            const active = selectedRoute === index
            const names = route.map((node) => machines[node - 1]?.name ?? `Stop ${node}`)
            return (
              <li key={`${index}-${route.join("-")}`}>
                <button
                  type="button"
                  onClick={() => selectRoute(active ? null : index)}
                  className="flex w-full flex-col gap-1 rounded-md px-2 py-1.5 text-left text-sm hover:bg-ink/5"
                >
                  <span className="flex items-center gap-3">
                    <span
                      className="inline-block size-2.5 rounded-full"
                      style={{ background: active ? SELECTED_ROUTE : ROUTE_COLORS[index % ROUTE_COLORS.length] }}
                    />
                    <span className="font-medium">Tanker {index + 1}</span>
                    <span className="truncate text-ink-soft">
                      {depot?.name ?? "Depot"}
                      {" → "}
                      {names.join(" → ")}
                    </span>
                  </span>
                  <span className="pl-5 text-xs text-ink-soft">
                    {path?.streets.length ? path.streets.join(", ") : "Unnamed roads"}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      </div>
    </motion.div>
  )
}

function formatKm(value: number) {
  if (!Number.isFinite(value)) return "—"
  return value.toFixed(2)
}
