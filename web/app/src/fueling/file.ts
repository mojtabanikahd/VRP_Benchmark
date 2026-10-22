import { z } from "zod"

import { MAX_IMAGE_BYTES } from "./icons"
import type { FuelFile } from "./store"

const imageSchema = z
  .string()
  .refine((value) => value.startsWith("data:image/"), "Each type needs an image")
  .refine((value) => value.length <= MAX_IMAGE_BYTES * 2, "An image is larger than 200 KB")

const machineTypeSchema = z.object({
  id: z.string().trim().min(1),
  name: z.string().trim().min(1),
  image: imageSchema,
})

const tankerTypeSchema = machineTypeSchema.extend({
  capacityL: z.number().int().positive(),
})

const depotSchema = z.object({
  id: z.string().trim().min(1),
  name: z.string().trim().min(1),
  lat: z.number().gte(-90).lte(90),
  lng: z.number().gte(-180).lte(180),
  windowOpenMin: z.number().gte(0).lte(24 * 60),
  windowCloseMin: z.number().gte(0).lte(24 * 60),
})

const machineSchema = z.object({
  id: z.string().trim().min(1),
  name: z.string().trim().min(1),
  machineTypeId: z.string().trim().min(1),
  lat: z.number().gte(-90).lte(90),
  lng: z.number().gte(-180).lte(180),
  fuelL: z.number().int().positive(),
  windowOpenMin: z.number().gte(0).lte(24 * 60),
  windowCloseMin: z.number().gte(0).lte(24 * 60),
  durationMin: z.number().nonnegative(),
})

const fileSchema = z.object({
  kind: z.literal("fueling"),
  version: z.literal(1),
  name: z.string().trim().min(1),
  machineTypes: z.array(machineTypeSchema).min(1),
  tankerTypes: z.array(tankerTypeSchema).min(1),
  tankerTypeId: z.string().trim().min(1),
  depot: depotSchema.nullable(),
  machines: z.array(machineSchema),
})

export function scenarioDocument(state: {
  name: string
  machineTypes: FuelFile["machineTypes"]
  tankerTypes: FuelFile["tankerTypes"]
  tankerTypeId: string
  depot: FuelFile["depot"]
  machines: FuelFile["machines"]
}): FuelFile {
  return {
    kind: "fueling",
    version: 1,
    name: state.name.trim() || "fueling",
    machineTypes: state.machineTypes,
    tankerTypes: state.tankerTypes,
    tankerTypeId: state.tankerTypeId,
    depot: state.depot,
    machines: state.machines,
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
  link.click()
  URL.revokeObjectURL(url)
}

export function parseScenarioFile(payload: unknown): FuelFile {
  const parsed = fileSchema.safeParse(payload)
  if (!parsed.success) {
    throw new Error(parsed.error.issues[0]?.message ?? "That file is not a fueling scenario")
  }
  const file = parsed.data
  if (!file.tankerTypes.some((item) => item.id === file.tankerTypeId)) {
    throw new Error("The selected tanker type is missing from the file")
  }
  const typeIds = new Set(file.machineTypes.map((item) => item.id))
  for (const machine of file.machines) {
    if (!typeIds.has(machine.machineTypeId)) {
      throw new Error(`${machine.name} refers to a machine type that is not in the file`)
    }
    if (machine.windowOpenMin > machine.windowCloseMin) {
      throw new Error(`${machine.name} window closes before it opens`)
    }
  }
  if (file.depot && file.depot.windowOpenMin > file.depot.windowCloseMin) {
    throw new Error("Depot shift closes before it opens")
  }
  return file
}
