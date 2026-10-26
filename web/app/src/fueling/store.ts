import { createContext, createElement, useContext, type ReactNode } from "react"
import { create, useStore, type StoreApi } from "zustand"

import type { Variant } from "../scenario/types"
import { copy, machineName } from "./copy"
import { MACHINE_ICON, TANKER_ICON } from "./icons"
import type { FuelDepot, FuelMachine, FuelResult, MachineType, MapMode, TankerType } from "./types"

const HISTORY_LIMIT = 100

export type FuelProfile = "fueling" | "studio"

export function usesTime(state: { profile: FuelProfile; variant: Variant }) {
  return state.profile === "fueling" || state.variant === "VRPTW"
}

export function usesManyDepots(state: { profile: FuelProfile; variant: Variant }) {
  return state.profile === "studio" && state.variant === "MDVRP"
}

function round6(value: number) {
  return Math.round(value * 1e6) / 1e6
}

function depotLabel(index: number) {
  return index === 0 ? copy.depot : `انبار ${index + 1}`
}

export interface FuelFile {
  kind: "fueling" | "studio"
  version: number
  name: string
  variant: Variant
  machineTypes: MachineType[]
  tanker: TankerType
  depot: FuelDepot | null
  depots: FuelDepot[]
  machines: FuelMachine[]
  solver: string | null
  timeBudgetS: number | null
  seed: number | null
}

interface ScenarioSnap {
  name: string
  variant: Variant
  machineTypes: MachineType[]
  tanker: TankerType
  depot: FuelDepot | null
  depots: FuelDepot[]
  machines: FuelMachine[]
  solver: string | null
  timeBudgetS: number
  seed: number
  solution: FuelResult | null
}

interface FuelState extends ScenarioSnap {
  profile: FuelProfile
  mode: MapMode
  selectedId: string | null
  selectedRoute: number | null
  jobError: string | null
  fileError: string | null
  fitToken: number
  focusId: string | null
  focusToken: number
  detailToken: number
  mapEpoch: number
  canUndo: boolean
  canRedo: boolean
  setName: (name: string) => void
  setVariant: (variant: Variant) => void
  setMode: (mode: MapMode) => void
  setSolver: (solver: string | null) => void
  ensureSolver: (solver: string) => void
  setTimeBudget: (seconds: number) => void
  setSeed: (seed: number) => void
  select: (id: string | null) => void
  inspect: (id: string) => void
  focusPoint: (id: string) => void
  focusStop: (id: string, routeIndex: number) => void
  selectRoute: (index: number | null) => void
  placeDepot: (lat: number, lng: number) => void
  moveDepot: (id: string, lat: number, lng: number) => void
  updateDepot: (id: string, patch: Partial<Omit<FuelDepot, "id">>) => void
  addMachine: (lat: number, lng: number) => void
  moveMachine: (id: string, lat: number, lng: number) => void
  updateMachine: (id: string, patch: Partial<Omit<FuelMachine, "id">>) => void
  removeSelected: () => void
  addMachineType: () => void
  updateMachineType: (id: string, patch: Partial<Omit<MachineType, "id">>) => void
  removeMachineType: (id: string) => void
  updateTanker: (patch: Partial<Omit<TankerType, "id">>) => void
  loadFile: (file: FuelFile) => void
  reset: () => void
  undo: () => void
  redo: () => void
  clearResult: () => void
  setSolution: (solution: FuelResult) => void
  setJobError: (message: string) => void
  setFileError: (message: string | null) => void
}

const cleared = { solution: null as FuelResult | null, jobError: null as string | null, selectedRoute: null as number | null }

function openDetails(state: { detailToken: number }, id: string) {
  return { selectedId: id, selectedRoute: null as number | null, detailToken: state.detailToken + 1 }
}

function scenarioSnap(state: ScenarioSnap): ScenarioSnap {
  return {
    name: state.name,
    variant: state.variant,
    machineTypes: state.machineTypes,
    tanker: state.tanker,
    depot: state.depot,
    depots: state.depots,
    machines: state.machines,
    solver: state.solver,
    timeBudgetS: state.timeBudgetS,
    seed: state.seed,
    solution: state.solution,
  }
}

function sameScenario(a: ScenarioSnap, b: ScenarioSnap) {
  return (
    a.name === b.name &&
    a.variant === b.variant &&
    a.timeBudgetS === b.timeBudgetS &&
    a.seed === b.seed &&
    a.solver === b.solver &&
    a.depot === b.depot &&
    a.depots === b.depots &&
    a.tanker === b.tanker &&
    a.machineTypes === b.machineTypes &&
    a.machines === b.machines &&
    a.solution === b.solution
  )
}

function alignDepots(depots: FuelDepot[], many: boolean) {
  if (many) return { depots, depot: depots[0] ?? null }
  const depot = depots[0] ?? null
  return { depot, depots: depot ? [depot] : [] }
}

export function createFuelStore(profile: FuelProfile) {
  let sequence = 1

  function nextId(prefix: string) {
    sequence += 1
    return `${prefix}${sequence}`
  }

  function rememberIds(ids: Array<string | null | undefined>) {
    for (const id of ids) {
      if (!id) continue
      const match = /(\d+)$/.exec(id)
      if (!match) continue
      const value = Number(match[1])
      if (value > sequence) sequence = value
    }
  }

  function freshMachineType(): MachineType {
    return { id: nextId("mt"), name: copy.machine, image: MACHINE_ICON, fuelL: 100, durationMin: 15 }
  }

  function freshTanker(): TankerType {
    return { id: nextId("tt"), name: copy.tanker, capacityL: 1000, image: TANKER_ICON }
  }

  function blankScenario(): ScenarioSnap {
    return {
      name: profile === "studio" ? copy.studioScenario : copy.defaultScenario,
      variant: profile === "studio" ? "CVRP" : "VRPTW",
      machineTypes: [freshMachineType()],
      tanker: freshTanker(),
      depot: null,
      depots: [],
      machines: [],
      solver: null,
      timeBudgetS: 10,
      seed: 0,
      solution: null,
    }
  }

  return create<FuelState>()((set, get) => {
    const past: ScenarioSnap[] = []
    const future: ScenarioSnap[] = []
    let recording = true
    let held: ScenarioSnap | null = null
    const flags = () => ({ canUndo: past.length > 0, canRedo: future.length > 0 })

    const commit: typeof set = (partial) => {
      const before = held ?? scenarioSnap(get())
      held = null
      set(partial)
      if (!recording) return
      const after = scenarioSnap(get())
      if (sameScenario(before, after)) return
      past.push(before)
      if (past.length > HISTORY_LIMIT) past.shift()
      future.length = 0
      recording = false
      set(flags())
      recording = true
    }

    const restore = (snap: ScenarioSnap) => {
      recording = false
      set({ ...snap, jobError: null, ...flags() })
      recording = true
    }

    return {
      ...blankScenario(),
      profile,
      mode: "select",
      selectedId: null,
      selectedRoute: null,
      jobError: null,
      fileError: null,
      fitToken: 0,
      focusId: null,
      focusToken: 0,
      detailToken: 0,
      mapEpoch: 0,
      canUndo: false,
      canRedo: false,
      setName: (name) => commit({ name }),
      setVariant: (variant) =>
        commit((state) => {
          if (state.profile !== "studio" || variant === state.variant) return {}
          const many = variant === "MDVRP"
          const source = state.depots.length > 0 ? state.depots : state.depot ? [state.depot] : []
          return { variant, ...alignDepots(many ? source : source.slice(0, 1), many), ...cleared }
        }),
      setMode: (mode) => set({ mode }),
      setSolver: (solver) => commit({ solver }),
      ensureSolver: (solver) => {
        recording = false
        set({ solver })
        recording = true
      },
      setTimeBudget: (seconds) => commit({ timeBudgetS: seconds }),
      setSeed: (seed) => commit({ seed: Math.max(0, Math.round(seed)) }),
      select: (id) => set({ selectedId: id, selectedRoute: null }),
      inspect: (id) => set((state) => openDetails(state, id)),
      focusPoint: (id) =>
        set((state) => ({
          ...openDetails(state, id),
          focusId: id,
          focusToken: state.focusToken + 1,
        })),
      focusStop: (id, routeIndex) =>
        set((state) => ({
          selectedId: id,
          selectedRoute: routeIndex,
          detailToken: state.detailToken + 1,
          focusId: id,
          focusToken: state.focusToken + 1,
        })),
      selectRoute: (index) => set({ selectedRoute: index }),
      placeDepot: (lat, lng) =>
        commit((state) => {
          const many = usesManyDepots(state)
          if (!many && state.depot) return openDetails(state, state.depot.id)
          const depot: FuelDepot = {
            id: nextId("d"),
            name: depotLabel(many ? state.depots.length : 0),
            lat: round6(lat),
            lng: round6(lng),
            windowOpenMin: 6 * 60,
            windowCloseMin: 22 * 60,
          }
          const depots = many ? [...state.depots, depot] : [depot]
          return {
            ...alignDepots(depots, many),
            ...openDetails(state, depot.id),
            fitToken: state.fitToken + 1,
            ...cleared,
          }
        }),
      moveDepot: (id, lat, lng) =>
        commit((state) => {
          const many = usesManyDepots(state)
          const depots = (state.depots.length > 0 ? state.depots : state.depot ? [state.depot] : []).map((depot) =>
            depot.id === id ? { ...depot, lat: round6(lat), lng: round6(lng) } : depot,
          )
          return { ...alignDepots(depots, many), ...cleared }
        }),
      updateDepot: (id, patch) =>
        commit((state) => {
          const many = usesManyDepots(state)
          const depots = (state.depots.length > 0 ? state.depots : state.depot ? [state.depot] : []).map((depot) =>
            depot.id === id ? { ...depot, ...patch, id: depot.id } : depot,
          )
          return { ...alignDepots(depots, many), ...cleared }
        }),
      addMachine: (lat, lng) =>
        commit((state) => {
          const type = state.machineTypes[0]
          if (!type) return {}
          const machine: FuelMachine = {
            id: nextId("m"),
            name: machineName(state.machines.length + 1),
            machineTypeId: type.id,
            lat: round6(lat),
            lng: round6(lng),
            fuelL: type.fuelL,
            windowOpenMin: 8 * 60,
            windowCloseMin: 16 * 60,
            durationMin: type.durationMin,
          }
          return {
            machines: [...state.machines, machine],
            ...openDetails(state, machine.id),
            ...cleared,
          }
        }),
      moveMachine: (id, lat, lng) =>
        commit((state) => ({
          machines: state.machines.map((machine) =>
            machine.id === id ? { ...machine, lat: round6(lat), lng: round6(lng) } : machine,
          ),
          ...cleared,
        })),
      updateMachine: (id, patch) =>
        commit((state) => ({
          machines: state.machines.map((machine) => (machine.id === id ? { ...machine, ...patch } : machine)),
          ...cleared,
        })),
      removeSelected: () =>
        commit((state) => {
          if (!state.selectedId) return {}
          const many = usesManyDepots(state)
          const depots = state.depots.length > 0 ? state.depots : state.depot ? [state.depot] : []
          if (depots.some((depot) => depot.id === state.selectedId)) {
            return {
              ...alignDepots(
                depots.filter((depot) => depot.id !== state.selectedId),
                many,
              ),
              selectedId: null,
              ...cleared,
            }
          }
          if (!state.machines.some((machine) => machine.id === state.selectedId)) return {}
          return {
            machines: state.machines.filter((machine) => machine.id !== state.selectedId),
            selectedId: null,
            ...cleared,
          }
        }),
      addMachineType: () => commit((state) => ({ machineTypes: [...state.machineTypes, freshMachineType()] })),
      updateMachineType: (id, patch) =>
        commit((state) => ({
          machineTypes: state.machineTypes.map((item) => (item.id === id ? { ...item, ...patch } : item)),
        })),
      removeMachineType: (id) =>
        commit((state) => {
          if (state.machineTypes.length <= 1) return {}
          const machineTypes = state.machineTypes.filter((item) => item.id !== id)
          const fallback = machineTypes[0].id
          return {
            machineTypes,
            machines: state.machines.map((machine) =>
              machine.machineTypeId === id ? { ...machine, machineTypeId: fallback } : machine,
            ),
          }
        }),
      updateTanker: (patch) =>
        commit((state) => ({
          tanker: { ...state.tanker, ...patch, id: state.tanker.id },
          ...(patch.capacityL !== undefined && patch.capacityL !== state.tanker.capacityL ? cleared : {}),
        })),
      loadFile: (file) =>
        commit((state) => {
          const variant = state.profile === "studio" ? file.variant : "VRPTW"
          const many = state.profile === "studio" && variant === "MDVRP"
          const loaded = many
            ? file.depots.length > 0
              ? file.depots
              : file.depot
                ? [file.depot]
                : []
            : file.depot
              ? [file.depot]
              : file.depots.slice(0, 1)
          rememberIds([
            file.tanker.id,
            ...loaded.map((depot) => depot.id),
            ...file.machineTypes.map((item) => item.id),
            ...file.machines.map((machine) => machine.id),
          ])
          return {
            name: file.name,
            variant,
            machineTypes: file.machineTypes,
            tanker: file.tanker,
            ...alignDepots(loaded, many),
            machines: file.machines,
            solver: file.solver ?? state.solver,
            timeBudgetS: file.timeBudgetS ?? state.timeBudgetS,
            seed: file.seed ?? state.seed,
            selectedId: null,
            fileError: null,
            fitToken: state.fitToken + 1,
            mapEpoch: state.mapEpoch + 1,
            ...cleared,
          }
        }),
      reset: () =>
        commit(() => {
          const current = get()
          return {
            ...blankScenario(),
            selectedId: null,
            selectedRoute: null,
            mode: "select" as const,
            jobError: null,
            fileError: null,
            focusId: null,
            fitToken: current.fitToken + 1,
            mapEpoch: current.mapEpoch + 1,
          }
        }),
      undo: () => {
        held = null
        const prev = past.pop()
        if (!prev) return
        future.push(scenarioSnap(get()))
        restore(prev)
      },
      redo: () => {
        held = null
        const next = future.pop()
        if (!next) return
        past.push(scenarioSnap(get()))
        restore(next)
      },
      clearResult: () => {
        if (held === null) held = scenarioSnap(get())
        recording = false
        set({ solution: null, jobError: null, selectedRoute: null })
        recording = true
      },
      setSolution: (solution) => commit({ solution, jobError: null, selectedRoute: null }),
      setJobError: (message) => commit({ jobError: message, solution: null }),
      setFileError: (message) => set({ fileError: message }),
    }
  })
}

export const fuelStore = createFuelStore("fueling")
export const studioStore = createFuelStore("studio")

const FuelStoreContext = createContext<StoreApi<FuelState>>(fuelStore)

export function FuelStoreProvider({ store, children }: { store: StoreApi<FuelState>; children: ReactNode }) {
  return createElement(FuelStoreContext.Provider, { value: store }, children)
}

export function useFuelApi() {
  return useContext(FuelStoreContext)
}

export function useFuel<T>(selector: (state: FuelState) => T): T {
  return useStore(useFuelApi(), selector)
}

function clockBody(
  point: { name: string; lat: number; lng: number },
  fallback: string,
  timed: boolean,
  clock?: { open: number; close: number },
) {
  const body: Record<string, unknown> = {
    name: point.name.trim() || fallback,
    lat: point.lat,
    lng: point.lng,
  }
  if (timed && clock) {
    body.window_open_min = clock.open
    body.window_close_min = clock.close
  }
  return body
}

export function fuelPayload(state: FuelState) {
  const tanker = state.tanker
  const timed = usesTime(state)
  const many = usesManyDepots(state)
  const depots = many ? state.depots : state.depot ? [state.depot] : []
  if (depots.length === 0 || !tanker || !state.solver) throw new Error(copy.notReady)
  if (many && depots.length < 2) throw new Error(copy.notReady)
  return {
    scenario: {
      name: state.name.trim() || (state.profile === "studio" ? copy.studioTitle : copy.appTitle),
      variant: state.profile === "studio" ? state.variant : "VRPTW",
      depot: many
        ? null
        : clockBody(depots[0], copy.depot, timed, { open: depots[0].windowOpenMin, close: depots[0].windowCloseMin }),
      depots: many ? depots.map((depot) => clockBody(depot, copy.depot, false)) : [],
      machines: state.machines.map((machine) => ({
        ...clockBody(machine, copy.machine, timed, { open: machine.windowOpenMin, close: machine.windowCloseMin }),
        machine_type_id: machine.machineTypeId,
        fuel_l: Math.round(machine.fuelL),
        ...(timed ? { duration_min: machine.durationMin } : {}),
      })),
      machine_types: state.machineTypes.map((item) => ({ id: item.id, name: item.name.trim() || copy.machine })),
      tanker_types: [
        {
          id: tanker.id,
          name: tanker.name.trim() || copy.tanker,
          capacity_l: Math.max(1, Math.round(tanker.capacityL)),
        },
      ],
      tanker_type_id: tanker.id,
    },
    solver: state.solver,
    time_budget_s: state.timeBudgetS,
    seed: state.seed,
  }
}
