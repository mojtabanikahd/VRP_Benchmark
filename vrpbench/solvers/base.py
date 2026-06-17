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

import numpy as np

from vrpbench.core.instance import Instance
from vrpbench.core.solution import Solution


class SolverError(RuntimeError):
    """Raised when a solver fails to produce a solution."""


def vrpmpd_max_vehicles(instance: Instance) -> int:
    """Generous-but-bounded fleet for VRPMPD, shared by all three adapters.

    Each vehicle must carry at most ``Q`` units; at minimum ``ceil(ΣD/Q)`` routes
    are needed to deliver all goods and ``ceil(ΣP/Q)`` routes to collect all
    pickups.  Adding 1 gives a comfortable headroom so the search is never
    infeasible due to the fleet cap, while keeping the pool much smaller than
    one-vehicle-per-customer (which blows OR-Tools/VROOM construction time).
    """
    total_d = int(instance.deliveries.sum()) if instance.deliveries is not None else 0
    total_p = int(instance.pickups.sum()) if instance.pickups is not None else 0
    return max(2, math.ceil(total_d / instance.capacity) + math.ceil(total_p / instance.capacity) + 1)


def lexicographic_fixed_cost(dist_int: np.ndarray, n: int) -> int:
    """Per-vehicle fixed cost that makes minimizing vehicles lexicographically primary.

    The cost is larger than any achievable total travel distance for this instance
    (``n * max_arc + 1``), so paying for one fewer vehicle always beats any distance
    saving.
    """
    return int(n) * int(dist_int.max()) + 1


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
