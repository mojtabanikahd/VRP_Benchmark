import { create } from "zustand"

import type { Preview, SolveResult } from "../lib/api"
import type { Role, ScenarioNode, Variant } from "./types"

let sequence = 1

function nextId() {
  sequence += 1
  return `n${sequence}`
}

export function makeNode(role: Role, x: number, y: number, demand = role === "depot" ? 0 : 1): ScenarioNode {
  return {
    id: nextId(),
    role,
    x: round2(x),
    y: round2(y),
    demand,
    ready: 0,
    due: role === "depot" ? 1000 : 200,
    service: role === "depot" ? 0 : 10,
  }
}

function round2(value: number) {
  return Math.round(value * 100) / 100
}

function orderNodes(nodes: ScenarioNode[]) {
  return [
    ...nodes.filter((node) => node.role === "depot"),
    ...nodes.filter((node) => node.role === "customer"),
  ]
}

interface StudioState {
  name: string
  variant: Variant
  capacity: number
  nodes: ScenarioNode[]
  selectedId: string | null
  selectedRoute: number | null
  solver: string | null
  timeBudgetS: number
  seed: number
  solution: SolveResult | null
  jobError: string | null
  uploadError: string | null
  fitToken: number
  setName: (name: string) => void
  setVariant: (variant: Variant) => void
  setCapacity: (capacity: number) => void
  setSolver: (solver: string | null) => void
  setTimeBudget: (seconds: number) => void
  setSeed: (seed: number) => void
  select: (id: string | null) => void
  selectRoute: (index: number | null) => void
  addCustomer: (x: number, y: number) => void
  addDepot: () => void
  moveNode: (id: string, x: number, y: number) => void
  updateNode: (id: string, patch: Partial<Omit<ScenarioNode, "id" | "role">>) => void
  removeSelected: () => void
  loadPreview: (preview: Preview) => void
  clearResult: () => void
  setSolution: (solution: SolveResult) => void
  setJobError: (message: string) => void
  setUploadError: (message: string | null) => void
  refit: () => void
}

export const useStudio = create<StudioState>((set) => ({
  name: "Untitled scenario",
  variant: "CVRP",
  capacity: 50,
  nodes: [makeNode("depot", 0, 0)],
  selectedId: null,
  selectedRoute: null,
  solver: null,
  timeBudgetS: 10,
  seed: 0,
  solution: null,
  jobError: null,
  uploadError: null,
  fitToken: 0,
  setName: (name) => set({ name }),
  setVariant: (variant) =>
    set((state) => {
      let nodes = orderNodes(state.nodes)
      const depots = nodes.filter((node) => node.role === "depot")
      const customers = nodes.filter((node) => node.role === "customer")
      if (variant === "MDVRP") {
        const primary = depots[0] ?? makeNode("depot", 0, 0)
        const secondary = depots[1] ?? makeNode("depot", primary.x + 20, primary.y)
        nodes = [primary, secondary, ...depots.slice(2), ...customers]
      } else {
        nodes = [depots[0] ?? makeNode("depot", 0, 0), ...customers]
      }
      return {
        variant,
        nodes,
        solution: null,
        jobError: null,
        selectedRoute: null,
        fitToken: state.fitToken + 1,
      }
    }),
  setCapacity: (capacity) => set({ capacity: Math.max(1, Math.round(capacity)) }),
  setSolver: (solver) => set({ solver }),
  setTimeBudget: (seconds) => set({ timeBudgetS: seconds }),
  setSeed: (seed) => set({ seed: Math.max(0, Math.round(seed)) }),
  select: (id) => set({ selectedId: id, selectedRoute: null }),
  selectRoute: (index) => set({ selectedRoute: index }),
  addCustomer: (x, y) =>
    set((state) => ({
      nodes: [...state.nodes, makeNode("customer", x, y)],
      solution: null,
      jobError: null,
    })),
  addDepot: () =>
    set((state) => {
      if (state.variant !== "MDVRP") return state
      const depots = state.nodes.filter((node) => node.role === "depot")
      const anchor = depots[depots.length - 1] ?? state.nodes[0]
      const depot = makeNode("depot", anchor.x + 15, anchor.y + 8)
      return {
        nodes: orderNodes([...state.nodes, depot]),
        solution: null,
        jobError: null,
        selectedId: depot.id,
        fitToken: state.fitToken + 1,
      }
    }),
  moveNode: (id, x, y) =>
    set((state) => ({
      nodes: state.nodes.map((node) =>
        node.id === id ? { ...node, x: round2(x), y: round2(y) } : node,
      ),
      solution: null,
      jobError: null,
    })),
  updateNode: (id, patch) =>
    set((state) => ({
      nodes: state.nodes.map((node) => {
        if (node.id !== id) return node
        const next = { ...node, ...patch }
        if (next.role === "depot") next.demand = 0
        return next
      }),
      solution: null,
      jobError: null,
    })),
  removeSelected: () =>
    set((state) => {
      const node = state.nodes.find((item) => item.id === state.selectedId)
      if (!node) return state
      const depots = state.nodes.filter((item) => item.role === "depot")
      if (node.role === "depot" && depots.length <= (state.variant === "MDVRP" ? 2 : 1)) {
        return state
      }
      return {
        nodes: state.nodes.filter((item) => item.id !== node.id),
        selectedId: null,
        solution: null,
        jobError: null,
      }
    }),
  loadPreview: (preview) =>
    set((state) => ({
      name: preview.scenario.name,
      variant: preview.scenario.variant,
      capacity: preview.scenario.capacity,
      nodes: orderNodes(
        preview.scenario.nodes.map((node) =>
          makeNode(node.role, node.x, node.y, node.demand),
        ).map((node, index) => {
          const source = preview.scenario.nodes[index]
          return {
            ...node,
            ready: source.ready ?? node.ready,
            due: source.due ?? node.due,
            service: source.service ?? node.service,
          }
        }),
      ),
      selectedId: null,
      selectedRoute: null,
      solution: null,
      jobError: null,
      uploadError: null,
      fitToken: state.fitToken + 1,
    })),
  clearResult: () => set({ solution: null, jobError: null }),
  setSolution: (solution) => set({ solution, jobError: null, selectedRoute: null }),
  setJobError: (message) => set({ jobError: message, solution: null }),
  setUploadError: (message) => set({ uploadError: message }),
  refit: () => set((state) => ({ fitToken: state.fitToken + 1 })),
}))

export function scenarioPayload(state: Pick<StudioState, "name" | "variant" | "capacity" | "nodes">) {
  return {
    name: state.name.trim() || "scenario",
    variant: state.variant,
    capacity: state.capacity,
    nodes: state.nodes.map((node) => ({
      role: node.role,
      x: node.x,
      y: node.y,
      demand: node.role === "depot" ? 0 : node.demand,
      ready: node.ready,
      due: node.due,
      service: node.service,
      geo: null,
    })),
  }
}
