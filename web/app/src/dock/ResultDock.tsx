import { motion } from "motion/react"

import { Badge } from "../components/ui/badge"
import { ROUTE_COLORS, SELECTED_ROUTE } from "../scenario/types"
import { useStudio } from "../scenario/store"

export function ResultDock() {
  const solution = useStudio((state) => state.solution)
  const jobError = useStudio((state) => state.jobError)
  const nodes = useStudio((state) => state.nodes)
  const variant = useStudio((state) => state.variant)
  const selectedRoute = useStudio((state) => state.selectedRoute)
  const selectRoute = useStudio((state) => state.selectRoute)

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
        Solved routes, verified distance, and constraint checks appear here.
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
        <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-ink-soft">Verified distance</p>
        <p className="font-display text-5xl leading-none text-ink">{formatNumber(solution.objective)}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Badge tone={solution.feasible ? "ok" : "bad"}>{solution.feasible ? "Feasible" : "Infeasible"}</Badge>
          <Badge>{solution.num_vehicles} vehicles</Badge>
          <Badge>{solution.runtime_s.toFixed(2)}s</Badge>
        </div>
        <p className="mt-3 text-xs text-ink-soft">
          Solver {formatNumber(solution.solver_objective)} · mismatch {formatNumber(solution.obj_mismatch)}
        </p>
      </div>
      <div className="min-h-0 overflow-auto">
        {solution.violations.length > 0 ? (
          <ul className="mb-3 space-y-1 text-sm text-copper">
            {solution.violations.map((violation) => (
              <li key={violation}>{violation}</li>
            ))}
          </ul>
        ) : null}
        <ul className="space-y-1">
          {solution.routes.map((route, index) => {
            if (route.length === 0) return null
            const depot = solution.route_depots[index] ?? 0
            const active = selectedRoute === index
            return (
              <li key={`${index}-${route.join("-")}`}>
                <button
                  type="button"
                  onClick={() => selectRoute(active ? null : index)}
                  className="flex w-full items-center gap-3 rounded-md px-2 py-1.5 text-left text-sm hover:bg-ink/5"
                >
                  <span
                    className="inline-block size-2.5 rounded-full"
                    style={{ background: active ? SELECTED_ROUTE : ROUTE_COLORS[index % ROUTE_COLORS.length] }}
                  />
                  <span className="font-medium">Route {index + 1}</span>
                  {variant === "MDVRP" ? <span className="text-ink-soft">Depot {depot}</span> : null}
                  <span className="truncate text-ink-soft">
                    {nodes[depot]?.role === "depot" ? "D" : depot}
                    {" → "}
                    {route.join(" → ")}
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

function formatNumber(value: number) {
  if (!Number.isFinite(value)) return "—"
  return Math.abs(value - Math.round(value)) < 1e-6 ? String(Math.round(value)) : value.toFixed(2)
}
