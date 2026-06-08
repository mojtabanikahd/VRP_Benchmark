"""VRP solution representation.

Routes are in canonical form: each route is an ordered list of *customer*
indices, with the depot implied at both ends (not stored). The evaluation layer
re-inserts the depot when recomputing the objective.
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

    def __post_init__(self) -> None:
        if self.num_vehicles == 0 and self.routes:
            object.__setattr__(
                self, "num_vehicles", sum(1 for r in self.routes if r)
            )
