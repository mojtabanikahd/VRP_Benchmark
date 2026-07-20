"""VRP solution representation.

Routes are in canonical form: each route is an ordered list of *customer*
indices, with the depot implied at both ends (not stored). The evaluation layer
re-inserts the depot when recomputing the objective.

For MDVRP, ``route_depots`` runs parallel to ``routes`` and names the depot index
each route starts and ends at. It is empty for single-depot variants (CVRP/VRPTW),
where the depot is always ``instance.depot``.

For PVRP, ``route_days`` runs parallel to ``routes`` and names the 0-indexed day
each route is operated on. It is empty for the non-periodic variants.

For SDVRP, ``route_deliveries`` gives, per route, the quantity delivered to each
customer on it. A customer whose demand is split appears in several ``routes``
entries, with its per-route quantities summing to the full demand. It is empty
for the non-split variants.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Solution:
    routes: list[list[int]]  # each route: ordered customer indices (no depot)
    objective: float  # total distance as reported by the solver
    feasible: bool  # solver's own claim; re-verified independently
    runtime_s: float  # wall-clock seconds spent inside solve()
    num_vehicles: int = field(default=0)  # number of non-empty routes
    # MDVRP only: depot index per route (parallel to ``routes``); empty otherwise.
    route_depots: list[int] = field(default_factory=list)
    # PVRP only: 0-indexed day per route (parallel to ``routes``); empty otherwise.
    route_days: list[int] = field(default_factory=list)
    # Legacy SDVRP detail field; canonical SDVRP R1 solvers do not populate it.
    route_vehicle_types: list[int] = field(default_factory=list)
    # SDVRP only: per-route {customer index -> delivered quantity}; empty otherwise.
    route_deliveries: list[dict[int, int]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.num_vehicles == 0 and self.routes:
            object.__setattr__(
                self, "num_vehicles", sum(1 for r in self.routes if r)
            )
