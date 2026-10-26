import { motion } from "motion/react"

import { Badge } from "../components/ui/badge"
import { cn } from "../lib/utils"
import { ROUTE_COLORS, SELECTED_ROUTE } from "../scenario/types"
import { copy, stopLabel, tankerLabel } from "./copy"
import { useFuel, usesManyDepots, usesTime } from "./store"
import { formatMinutes, formatRange } from "./time"
import type { FuelResult } from "./types"

export function FuelDock() {
  const solution = useFuel((state) => state.solution)
  const jobError = useFuel((state) => state.jobError)
  const timed = useFuel((state) => usesTime(state))
  const many = useFuel((state) => usesManyDepots(state))
  const depot = useFuel((state) => state.depot)
  const depots = useFuel((state) => state.depots)
  const machines = useFuel((state) => state.machines)
  const selectedRoute = useFuel((state) => state.selectedRoute)
  const selectRoute = useFuel((state) => state.selectRoute)
  const focusStop = useFuel((state) => state.focusStop)

  if (jobError) {
    return (
      <div className="flex h-full items-center px-6">
        <p className="text-sm text-copper">{jobError}</p>
      </div>
    )
  }

  if (!solution) {
    return <div className="flex h-full items-center px-6 text-sm text-ink-soft">{copy.emptySolution}</div>
  }

  const points = many ? depots : depot ? [depot] : []
  const depotCount = Math.max(points.length, 1)

  return (
    <motion.div
      className="grid h-full grid-cols-[220px_minmax(0,1fr)] gap-6 px-6 py-4"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
    >
      <div>
        <p className="text-[11px] font-medium tracking-[0.16em] text-ink-soft">{copy.drivingDistance}</p>
        <p className="font-display text-5xl leading-none text-ink">{formatKm(solution.objective)}</p>
        <p className="mt-1 text-xs text-ink-soft">{copy.kilometers}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Badge tone={solution.feasible ? "ok" : "bad"}>{solution.feasible ? copy.feasible : copy.infeasible}</Badge>
          <Badge>
            {solution.num_vehicles} {copy.tanker}
          </Badge>
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
            const clock = routeClock(solution, index)
            const legs = solution.leg_km?.[index] ?? []
            const routeDepot = points[solution.route_depots?.[index] ?? 0] ?? points[0]
            const depotName = routeDepot?.name ?? copy.depot
            const color = active ? SELECTED_ROUTE : ROUTE_COLORS[index % ROUTE_COLORS.length]
            return (
              <li key={`${index}-${route.join("-")}`}>
                <div
                  className={cn(
                    "w-full rounded-md border px-3 py-2",
                    active ? "border-ink bg-ink/[0.04]" : "border-line hover:border-ink/30",
                  )}
                >
                  <button
                    type="button"
                    onClick={() => selectRoute(active ? null : index)}
                    className="w-full text-start"
                  >
                    <span className="flex items-center justify-between gap-3">
                      <span className="flex items-center gap-2">
                        <span className="inline-block size-2.5 rounded-full" style={{ background: color }} />
                        <span className="text-sm font-medium">
                          {tankerLabel(index + 1)}
                          {many && routeDepot ? ` · ${routeDepot.name}` : ""}
                        </span>
                      </span>
                      <span className="text-sm tabular-nums text-ink">
                        {formatKm(solution.route_km?.[index])} {copy.kilometers}
                      </span>
                    </span>
                  </button>
                  <ol className="mt-2 space-y-1 border-s border-line ps-3">
                    <li>
                      <StopButton
                        name={depotName}
                        when={timed ? `${copy.depart} ${formatMinutes(clock.depart)}` : ""}
                        onClick={routeDepot ? () => focusStop(routeDepot.id, index) : undefined}
                      />
                    </li>
                    {route.map((node, stop) => {
                      const machine = machines[node - depotCount]
                      return (
                        <li key={`${node}-${stop}`} className="space-y-1">
                          <p className="text-xs tabular-nums text-ink-soft">
                            {formatKm(legs[stop])} {copy.kilometers}
                          </p>
                          <StopButton
                            name={machine?.name ?? stopLabel(node)}
                            when={timed ? stopRange(clock.arrivals[stop], clock.leaves[stop]) : ""}
                            onClick={machine ? () => focusStop(machine.id, index) : undefined}
                          />
                        </li>
                      )
                    })}
                    <li className="space-y-1">
                      <p className="text-xs tabular-nums text-ink-soft">
                        {formatKm(legs[route.length])} {copy.kilometers}
                      </p>
                      <StopButton
                        name={depotName}
                        when={timed ? `${copy.return} ${formatMinutes(clock.back)}` : ""}
                        onClick={routeDepot ? () => focusStop(routeDepot.id, index) : undefined}
                      />
                    </li>
                  </ol>
                  <p className="mt-2 text-xs text-ink-soft">
                    {path?.streets.length ? path.streets.join("، ") : copy.unnamedRoads}
                  </p>
                </div>
              </li>
            )
          })}
        </ul>
      </div>
    </motion.div>
  )
}

function StopButton({ name, when, onClick }: { name: string; when: string; onClick?: () => void }) {
  return (
    <button type="button" onClick={onClick} disabled={!onClick} className="flex w-full items-baseline justify-between gap-3 text-start text-sm">
      <span className="truncate">{name}</span>
      <span className="shrink-0 tabular-nums text-ink-soft">{when}</span>
    </button>
  )
}

function formatKm(value: number | undefined) {
  if (value === undefined || !Number.isFinite(value)) return "—"
  return value.toFixed(2)
}

function routeClock(solution: FuelResult, index: number) {
  return {
    depart: solution.depart_min?.[index],
    arrivals: solution.arrivals_min?.[index] ?? [],
    leaves: solution.leaves_min?.[index] ?? [],
    back: solution.return_min?.[index],
  }
}

function stopRange(arrive: number | undefined, leave: number | undefined) {
  if (arrive === undefined || leave === undefined || !Number.isFinite(arrive) || !Number.isFinite(leave)) return ""
  return formatRange(arrive, leave)
}
