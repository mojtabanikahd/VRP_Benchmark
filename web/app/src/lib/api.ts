import type { Variant } from "../scenario/types"

export interface SolverInfo {
  name: string
  version: string
}

export interface Catalog {
  variants: { variant: Variant; solvers: SolverInfo[] }[]
}

export interface ScenarioPayload {
  name: string
  variant: Variant
  capacity: number
  nodes: {
    role: "depot" | "customer"
    x: number
    y: number
    demand: number
    ready: number | null
    due: number | null
    service: number | null
    geo: null
  }[]
}

export interface SolveResult {
  routes: number[][]
  route_depots: number[]
  objective: number
  solver_objective: number
  num_vehicles: number
  runtime_s: number
  obj_mismatch: number
  feasible: boolean
  violations: string[]
  solver_version: string
}

export interface JobView {
  id: string
  status: "queued" | "running" | "ok" | "error"
  error: string | null
  result: SolveResult | null
}

export interface Preview {
  ok: boolean
  scenario: ScenarioPayload
  num_depots: number
  num_customers: number
  distance_kind: string
}

export async function readError(response: Response): Promise<string> {
  const text = await response.text()
  try {
    const body = JSON.parse(text) as { detail?: unknown }
    if (typeof body.detail === "string") return body.detail
    if (Array.isArray(body.detail)) {
      return body.detail
        .map((item) => {
          if (item && typeof item === "object" && "msg" in item) {
            return String((item as { msg: unknown }).msg)
          }
          return ""
        })
        .filter(Boolean)
        .join("; ")
    }
  } catch {
    /* response was not JSON */
  }
  return text || response.statusText
}

export async function fetchCatalog(): Promise<Catalog> {
  const response = await fetch("/api/catalog")
  if (!response.ok) throw new Error(await readError(response))
  return response.json() as Promise<Catalog>
}

export async function uploadInstance(variant: Variant, file: File): Promise<Preview> {
  const body = new FormData()
  body.set("variant", variant)
  body.set("file", file)
  const response = await fetch("/api/instances/upload", { method: "POST", body })
  if (!response.ok) throw new Error(await readError(response))
  return response.json() as Promise<Preview>
}

export async function createJob(payload: {
  scenario: ScenarioPayload
  solver: string
  time_budget_s: number
  seed: number
}): Promise<JobView> {
  const response = await fetch("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!response.ok) throw new Error(await readError(response))
  return response.json() as Promise<JobView>
}

export async function fetchJob(id: string): Promise<JobView> {
  const response = await fetch(`/api/jobs/${id}`)
  if (!response.ok) throw new Error(await readError(response))
  return response.json() as Promise<JobView>
}
