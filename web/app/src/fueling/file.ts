import { z } from "zod"

import { copy, missingType, windowOrder } from "./copy"
import { MAX_IMAGE_BYTES } from "./icons"
import type { FuelFile } from "./store"

const imageSchema = z
  .string()
  .refine((value) => value.startsWith("data:image/"), copy.imageRequired)
  .refine((value) => value.length <= MAX_IMAGE_BYTES * 2, copy.imageTooLarge)

function label(fallback: string) {
  return z.preprocess((value) => {
    if (typeof value !== "string") return value
    const text = value.trim()
    return text || fallback
  }, z.string().min(1))
}

const wholeLiters = z.preprocess((value) => {
  if (typeof value !== "number" || !Number.isFinite(value)) return value
  return Math.max(1, Math.round(value))
}, z.number().int().positive())

const minutesField = z.preprocess((value) => {
  if (typeof value !== "number" || !Number.isFinite(value)) return value
  return Math.max(0, value)
}, z.number().nonnegative())

const clockField = z.number().gte(0).lte(24 * 60)

const machineTypeSchema = z.object({
  id: z.string().trim().min(1),
  name: label(copy.machine),
  image: imageSchema,
  fuelL: wholeLiters.default(100),
  durationMin: minutesField.default(15),
})

const tankerSchema = z.object({
  id: z.string().trim().min(1),
  name: label(copy.tanker),
  image: imageSchema,
  capacityL: wholeLiters,
})

const depotSchema = z.object({
  id: z.string().trim().min(1),
  name: label(copy.depot),
  lat: z.number().gte(-90).lte(90),
  lng: z.number().gte(-180).lte(180),
  windowOpenMin: clockField,
  windowCloseMin: clockField,
})

const machineSchema = z.object({
  id: z.string().trim().min(1),
  name: label(copy.machine),
  machineTypeId: z.string().trim().min(1),
  lat: z.number().gte(-90).lte(90),
  lng: z.number().gte(-180).lte(180),
  fuelL: wholeLiters,
  windowOpenMin: clockField,
  windowCloseMin: clockField,
  durationMin: minutesField,
})

const shared = {
  kind: z.literal("fueling"),
  name: label(copy.appTitle),
  machineTypes: z.array(machineTypeSchema).min(1),
  depot: depotSchema.nullable(),
  machines: z.array(machineSchema),
}

const fileV1Schema = z.object({
  ...shared,
  version: z.literal(1),
  tankerTypes: z.array(tankerSchema).min(1),
  tankerTypeId: z.string().trim().min(1),
})

const solverField = z.preprocess((value) => {
  if (value == null) return null
  if (typeof value !== "string") return value
  const text = value.trim()
  return text || null
}, z.string().min(1).nullable())

const fileV2Schema = z.object({
  ...shared,
  version: z.literal(2),
  tanker: tankerSchema,
  solver: solverField.nullable().optional().default(null),
  timeBudgetS: z.number().gt(0).lte(300).optional(),
  seed: z
    .preprocess((value) => {
      if (typeof value !== "number" || !Number.isFinite(value)) return value
      return Math.max(0, Math.round(value))
    }, z.number().int().nonnegative())
    .optional(),
})

export function scenarioDocument(state: {
  name: string
  machineTypes: FuelFile["machineTypes"]
  tanker: FuelFile["tanker"]
  depot: FuelFile["depot"]
  machines: FuelFile["machines"]
  solver: string | null
  timeBudgetS: number
  seed: number
}): FuelFile {
  return {
    kind: "fueling",
    version: 2,
    name: state.name.trim() || "fueling",
    machineTypes: state.machineTypes,
    tanker: state.tanker,
    depot: state.depot,
    machines: state.machines,
    solver: state.solver,
    timeBudgetS: state.timeBudgetS,
    seed: state.seed,
  }
}

export function downloadScenario(state: Parameters<typeof scenarioDocument>[0]) {
  const document = scenarioDocument(state)
  const blob = new Blob([JSON.stringify(document, null, 2)], { type: "application/json" })
  const url = URL.createObjectURL(blob)
  const link = window.document.createElement("a")
  const slug = document.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "fueling"
  link.href = url
  link.download = `${slug}.fueling.json`
  window.document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1500)
}

export function parseScenarioText(text: string): FuelFile {
  let payload: unknown
  try {
    payload = JSON.parse(text.replace(/^\uFEFF/, "")) as unknown
  } catch {
    throw new Error(copy.notFuelFile)
  }
  return parseScenarioFile(payload)
}

export function parseScenarioFile(payload: unknown): FuelFile {
  const version = payload && typeof payload === "object" ? (payload as { version?: unknown }).version : undefined
  if (version === 1) return finish(parseV1(payload))
  if (version === 2) return finish(parseV2(payload))
  throw new Error(copy.notFuelFile)
}

function parseV1(payload: unknown): FuelFile {
  const parsed = fileV1Schema.safeParse(payload)
  if (!parsed.success) {
    throw new Error(parsed.error.issues[0]?.message ?? copy.notFuelFile)
  }
  const file = parsed.data
  const tanker = file.tankerTypes.find((item) => item.id === file.tankerTypeId)
  if (!tanker) throw new Error(copy.missingTanker)
  return {
    kind: "fueling",
    version: 2,
    name: file.name,
    machineTypes: file.machineTypes,
    tanker,
    depot: file.depot,
    machines: file.machines,
    solver: null,
    timeBudgetS: null,
    seed: null,
  }
}

function parseV2(payload: unknown): FuelFile {
  const parsed = fileV2Schema.safeParse(payload)
  if (!parsed.success) {
    throw new Error(parsed.error.issues[0]?.message ?? copy.notFuelFile)
  }
  const file = parsed.data
  return {
    kind: "fueling",
    version: 2,
    name: file.name,
    machineTypes: file.machineTypes,
    tanker: file.tanker,
    depot: file.depot,
    machines: file.machines,
    solver: file.solver,
    timeBudgetS: file.timeBudgetS ?? null,
    seed: file.seed ?? null,
  }
}

function finish(file: FuelFile): FuelFile {
  const typeIds = new Set(file.machineTypes.map((item) => item.id))
  for (const machine of file.machines) {
    if (!typeIds.has(machine.machineTypeId)) {
      throw new Error(missingType(machine.name))
    }
    if (machine.windowOpenMin > machine.windowCloseMin) {
      throw new Error(windowOrder(machine.name))
    }
  }
  if (file.depot && file.depot.windowOpenMin > file.depot.windowCloseMin) {
    throw new Error(copy.depotWindow)
  }
  return file
}
