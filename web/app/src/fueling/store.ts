import { create } from "zustand"

import { copy, machineName } from "./copy"
import { MACHINE_ICON, TANKER_ICON } from "./icons"
import type { FuelDepot, FuelMachine, FuelResult, MachineType, MapMode, TankerType } from "./types"

const HISTORY_LIMIT = 100

let sequence = 1

function nextId(prefix: string) {
  sequence += 1
  return `${prefix}${sequence}`
}

export function rememberIds(ids: Array<string | null | undefined>) {
  for (const id of ids) {
    if (!id) continue
    const match = /(\d+)$/.exec(id)
    if (!match) continue
    const value = Number(match[1])
    if (value > sequence) sequence = value
  }
}

function round6(value: number) {
  return Math.round(value * 1e6) / 1e6
}

export interface FuelFile {
  kind: "fueling"
  version: 2
  name: string
  machineTypes: MachineType[]
  tanker: TankerType
  depot: FuelDepot | null
  machines: FuelMachine[]
  solver: string | null
  timeBudgetS: number | null
  seed: number | null
}

interface ScenarioSnap {
  name: string
  machineTypes: MachineType[]
  tanker: TankerType
  depot: FuelDepot | null
  machines: FuelMachine[]
  solver: string | null
  timeBudgetS: number
  seed: number
  solution: FuelResult | null
}

interface FuelState extends ScenarioSnap {
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
  moveDepot: (lat: number, lng: number) => void
  updateDepot: (patch: Partial<Omit<FuelDepot, "id">>) => void
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

function freshMachineType(): MachineType {
  return { id: nextId("mt"), name: copy.machine, image: MACHINE_ICON, fuelL: 100, durationMin: 15 }
}

function freshTanker(): TankerType {
  return { id: nextId("tt"), name: copy.tanker, capacityL: 1000, image: TANKER_ICON }
}

function openDetails(state: { detailToken: number }, id: string) {
  return { selectedId: id, selectedRoute: null as number | null, detailToken: state.detailToken + 1 }
}

function scenarioSnap(state: ScenarioSnap): ScenarioSnap {
  return {
    name: state.name,
    machineTypes: state.machineTypes,
    tanker: state.tanker,
    depot: state.depot,
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
    a.timeBudgetS === b.timeBudgetS &&
    a.seed === b.seed &&
    a.solver === b.solver &&
    a.depot === b.depot &&
    a.tanker === b.tanker &&
    a.machineTypes === b.machineTypes &&
    a.machines === b.machines &&
    a.solution === b.solution
  )
}

const firstMachine = freshMachineType()
const firstTanker = freshTanker()

const INITIAL: ScenarioSnap = {
  name: copy.defaultScenario,
  machineTypes: [firstMachine],
  tanker: firstTanker,
  depot: null,
  machines: [],
  solver: null,
  timeBudgetS: 10,
  seed: 0,
  solution: null,
}

function blankScenario(): ScenarioSnap {
  return {
    name: INITIAL.name,
    machineTypes: INITIAL.machineTypes.map((item) => ({ ...item })),
    tanker: { ...INITIAL.tanker },
    depot: null,
    machines: [],
    solver: null,
    timeBudgetS: INITIAL.timeBudgetS,
    seed: INITIAL.seed,
    solution: null,
  }
}

export const useFuel = create<FuelState>()((set, get) => {
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
        if (state.depot) return openDetails(state, state.depot.id)
        const depot: FuelDepot = {
          id: nextId("d"),
          name: copy.depot,
          lat: round6(lat),
          lng: round6(lng),
          windowOpenMin: 6 * 60,
          windowCloseMin: 22 * 60,
        }
        return { depot, ...openDetails(state, depot.id), fitToken: state.fitToken + 1, ...cleared }
      }),
    moveDepot: (lat, lng) =>
      commit((state) => ({
        depot: state.depot ? { ...state.depot, lat: round6(lat), lng: round6(lng) } : null,
        ...cleared,
      })),
    updateDepot: (patch) =>
      commit((state) => ({
        depot: state.depot ? { ...state.depot, ...patch, id: state.depot.id } : null,
        ...cleared,
      })),
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
        if (state.selectedId === state.depot?.id) {
          return { depot: null, selectedId: null, ...cleared }
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
        rememberIds([
          file.tanker.id,
          file.depot?.id,
          ...file.machineTypes.map((item) => item.id),
          ...file.machines.map((machine) => machine.id),
        ])
        return {
          name: file.name,
          machineTypes: file.machineTypes,
          tanker: file.tanker,
          depot: file.depot,
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
      commit((state) => ({
        ...blankScenario(),
        selectedId: null,
        selectedRoute: null,
        mode: "select",
        jobError: null,
        fileError: null,
        focusId: null,
        fitToken: state.fitToken + 1,
        mapEpoch: state.mapEpoch + 1,
      })),
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

export function fuelPayload(state: FuelState) {
  const depot = state.depot
  const tanker = state.tanker
  if (!depot || !tanker || !state.solver) throw new Error(copy.notReady)
  return {
    scenario: {
      name: state.name.trim() || copy.appTitle,
      depot: {
        name: depot.name.trim() || copy.depot,
        lat: depot.lat,
        lng: depot.lng,
        window_open_min: depot.windowOpenMin,
        window_close_min: depot.windowCloseMin,
      },
      machines: state.machines.map((machine) => ({
        name: machine.name.trim() || copy.machine,
        machine_type_id: machine.machineTypeId,
        lat: machine.lat,
        lng: machine.lng,
        fuel_l: Math.round(machine.fuelL),
        window_open_min: machine.windowOpenMin,
        window_close_min: machine.windowCloseMin,
        duration_min: machine.durationMin,
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
