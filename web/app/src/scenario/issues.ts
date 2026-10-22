import type { ScenarioNode, Variant } from "./types"

export function scenarioIssues(input: {
  variant: Variant
  capacity: number
  nodes: ScenarioNode[]
}): string[] {
  const issues: string[] = []
  const depots = input.nodes.filter((node) => node.role === "depot")
  const customers = input.nodes.filter((node) => node.role === "customer")
  if (input.capacity < 1) issues.push("Capacity must be at least 1.")
  if (input.variant === "MDVRP" && depots.length < 2) {
    issues.push("MDVRP needs at least two depots.")
  }
  if (input.variant !== "MDVRP" && depots.length !== 1) {
    issues.push(`${input.variant} needs exactly one depot.`)
  }
  if (customers.length === 0) issues.push("Add at least one customer.")
  for (const node of customers) {
    if (node.demand > input.capacity) {
      issues.push(`A customer demand of ${node.demand} is above capacity ${input.capacity}.`)
      break
    }
  }
  if (input.variant === "VRPTW") {
    const invalid = input.nodes.find((node) => node.ready > node.due)
    if (invalid) issues.push("A time window ends before it starts.")
  }
  return issues
}
