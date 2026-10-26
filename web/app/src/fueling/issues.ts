import { copy, durationDoesNotFit, fuelExceedsTank, negativeDuration, noMachineType, wholeFuel, windowOrder } from "./copy"
import type { FuelDepot, FuelMachine, MachineType, TankerType } from "./types"

export function fuelIssues(input: {
  depot: FuelDepot | null
  depots: FuelDepot[]
  machines: FuelMachine[]
  machineTypes: MachineType[]
  tanker: TankerType | null
  solver: string | null
  timed: boolean
  manyDepots: boolean
}): string[] {
  const issues: string[] = []
  const tanker = input.tanker
  if (!tanker) issues.push(copy.setTanker)
  else if (!Number.isInteger(tanker.capacityL) || tanker.capacityL < 1) {
    issues.push(copy.wholeCapacity)
  }
  if (input.manyDepots) {
    if (input.depots.length < 2) issues.push(copy.needTwoDepots)
  } else if (!input.depot) issues.push(copy.placeDepot)
  if (input.machines.length === 0) issues.push(copy.placeMachineIssue)
  if (input.timed && input.depot && input.depot.windowOpenMin > input.depot.windowCloseMin) {
    issues.push(copy.depotWindow)
  }
  const typeIds = new Set(input.machineTypes.map((item) => item.id))
  for (const machine of input.machines) {
    if (!typeIds.has(machine.machineTypeId)) issues.push(noMachineType(machine.name))
    if (input.timed && machine.windowOpenMin > machine.windowCloseMin) {
      issues.push(windowOrder(machine.name))
    }
    if (input.timed && machine.durationMin > machine.windowCloseMin - machine.windowOpenMin) {
      issues.push(durationDoesNotFit(machine.name))
    }
    if (!Number.isInteger(machine.fuelL) || machine.fuelL < 1) {
      issues.push(wholeFuel(machine.name))
    } else if (tanker && machine.fuelL > tanker.capacityL) {
      issues.push(fuelExceedsTank(machine.name))
    }
    if (input.timed && machine.durationMin < 0) issues.push(negativeDuration(machine.name))
  }
  if (!input.solver) issues.push(copy.chooseSolver)
  return issues
}
