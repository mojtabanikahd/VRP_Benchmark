export type MapMode = "select" | "depot" | "machine"

export interface MachineType {
  id: string
  name: string
  image: string
  fuelL: number
  durationMin: number
}

export interface TankerType {
  id: string
  name: string
  capacityL: number
  image: string
}

export interface FuelDepot {
  id: string
  name: string
  lat: number
  lng: number
  windowOpenMin: number
  windowCloseMin: number
}

export interface FuelMachine {
  id: string
  name: string
  machineTypeId: string
  lat: number
  lng: number
  fuelL: number
  windowOpenMin: number
  windowCloseMin: number
  durationMin: number
}

export interface RoadPath {
  stops: number[]
  geometry: { type: "LineString"; coordinates: [number, number][] }
  streets: string[]
}

export interface FuelResult {
  routes: number[][]
  objective: number
  solver_objective: number
  num_vehicles: number
  runtime_s: number
  obj_mismatch: number
  feasible: boolean
  violations: string[]
  solver_version: string
  paths: RoadPath[]
}
