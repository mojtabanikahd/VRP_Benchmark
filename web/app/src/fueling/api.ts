import { readError } from "../lib/api"
import type { FuelResult } from "./types"

export interface FuelSolverInfo {
  name: string
  version: string
}

export async function fetchFuelCatalog(): Promise<{ solvers: FuelSolverInfo[] }> {
  const response = await fetch("/api/fueling/catalog")
  if (!response.ok) throw new Error(await readError(response))
  return response.json() as Promise<{ solvers: FuelSolverInfo[] }>
}

export async function createFuelJob(payload: unknown): Promise<{ id: string; status: string }> {
  const response = await fetch("/api/fueling/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!response.ok) throw new Error(await readError(response))
  return response.json() as Promise<{ id: string; status: string }>
}

export async function fetchFuelJob(id: string): Promise<{
  id: string
  status: "queued" | "running" | "ok" | "error"
  error: string | null
  result: FuelResult | null
}> {
  const response = await fetch(`/api/jobs/${id}`)
  if (!response.ok) throw new Error(await readError(response))
  return response.json() as Promise<{
    id: string
    status: "queued" | "running" | "ok" | "error"
    error: string | null
    result: FuelResult | null
  }>
}
