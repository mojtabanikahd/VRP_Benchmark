"""The strict solver interface that makes all solvers interchangeable.

Every solver exposes a single method:

    solve(instance, *, time_budget_s, seed) -> Solution

No solver-specific arguments leak into this signature; engine-specific knobs
live as constructor defaults on the adapter. The runner only ever depends on
this protocol, never on a concrete solver.
"""

from __future__ import annotations

import math
from typing import Protocol, runtime_checkable

from vrpbench.core.instance import Instance
from vrpbench.core.solution import Solution


class SolverError(RuntimeError):
    """Raised when a solver fails to produce a solution."""


def mdvrp_vehicles_per_depot(instance: Instance) -> int:
    """A generous-but-bounded per-depot fleet for MDVRP, shared by all adapters.

    Let ``R = ceil(total_demand / capacity)`` be the capacity lower bound on the
    number of routes. Giving *each* of the ``t >= 2`` depots ``R`` vehicles yields
    ``t * R >= 2R`` total route slots — more than any first-fit packing of all
    customers ever needs (< ``1.7R``) — and since depot assignment is open those
    routes can always be distributed with at most ``R`` per depot. So a feasible
    solution is guaranteed however the search spreads customers across depots,
    while the fleet stays far smaller than one-vehicle-per-customer (which makes
    OR-Tools' construction and VROOM's local search blow past the time budget).
    """
    total_demand = int(instance.demands.sum())
    return max(1, math.ceil(total_demand / instance.capacity))


@runtime_checkable
class Solver(Protocol):
    name: str
    #: Variants this solver supports, e.g. ("CVRP", "VRPTW").
    supported_variants: tuple[str, ...]

    def solve(self, instance: Instance, *, time_budget_s: float, seed: int) -> Solution:
        """Solve ``instance`` within ``time_budget_s`` wall-clock seconds."""
        ...

    def version(self) -> str:
        """Return the underlying engine version (recorded for reproducibility)."""
        ...
