import type { FuelDepot, FuelMachine, MachineType, TankerType } from "./types"

export function fuelIssues(input: {
  depot: FuelDepot | null
  machines: FuelMachine[]
  machineTypes: MachineType[]
  tankerTypes: TankerType[]
  tankerTypeId: string
  solver: string | null
}): string[] {
  const issues: string[] = []
  const tanker = input.tankerTypes.find((item) => item.id === input.tankerTypeId) ?? null
  if (!tanker) issues.push("Choose a tanker type")
  if (!input.depot) issues.push("Place a depot on the map")
  if (input.machines.length === 0) issues.push("Place at least one machine")
  if (input.depot && input.depot.windowOpenMin > input.depot.windowCloseMin) {
    issues.push("Depot shift closes before it opens")
  }
  const typeIds = new Set(input.machineTypes.map((item) => item.id))
  for (const machine of input.machines) {
    if (!typeIds.has(machine.machineTypeId)) issues.push(`${machine.name} has no machine type`)
    if (machine.windowOpenMin > machine.windowCloseMin) {
      issues.push(`${machine.name} window closes before it opens`)
    }
    if (!Number.isInteger(machine.fuelL) || machine.fuelL < 1) {
      issues.push(`${machine.name} needs a whole-liter fuel demand`)
    } else if (tanker && machine.fuelL > tanker.capacityL) {
      issues.push(`${machine.name} needs more fuel than the tanker holds`)
    }
    if (machine.durationMin < 0) issues.push(`${machine.name} has a negative refueling duration`)
  }
  if (!input.solver) issues.push("Choose a solver")
  return issues
}
