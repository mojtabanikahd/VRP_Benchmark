export type Variant = "CVRP" | "VRPTW" | "MDVRP"
export type Role = "depot" | "customer"

export interface ScenarioNode {
  id: string
  role: Role
  x: number
  y: number
  demand: number
  ready: number
  due: number
  service: number
}

export const VARIANTS: Variant[] = ["CVRP", "VRPTW", "MDVRP"]

/** Okabe–Ito, used only for solved routes. */
export const ROUTE_COLORS = [
  "#0072B2",
  "#D55E00",
  "#009E73",
  "#CC79A7",
  "#56B4E9",
  "#E69F00",
  "#000000",
  "#F0E442",
] as const

export const SELECTED_ROUTE = "#c4622d"
