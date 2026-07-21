"""A Priori Adaptive Splitting Algorithm adapters for SDVRP.

AASA discretises every SDVRP demand into colocated virtual customers, producing
a CVRP that can be solved by an existing adapter.  Decoding restores original
customer indices and authoritative per-route delivery quantities.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from functools import reduce

import numpy as np

from vrpbench.core.evaluate import route_distance
from vrpbench.core.instance import CVRP, SDVRP, Instance
from vrpbench.core.solution import Solution
from vrpbench.solvers.base import Solver, SolverError


@dataclass(frozen=True)
class AASATransformation:
    """A transformed CVRP plus its virtual-to-original node mapping."""

    instance: Instance
    parents: tuple[int, ...]
    quantities: tuple[int, ...]


def _ffd_vehicle_bound(fragments: list[int], capacity: int) -> int:
    """Return a feasible route-slot count from first-fit decreasing packing."""
    loads: list[int] = []
    for fragment in sorted(fragments, reverse=True):
        for index, load in enumerate(loads):
            if load + fragment <= capacity:
                loads[index] += fragment
                break
        else:
            loads.append(fragment)
    return max(1, len(loads))


def transform_aasa(instance: Instance) -> AASATransformation:
    """Transform a homogeneous SDVRP instance into the fixed AASA CVRP."""
    if instance.variant != SDVRP:
        raise SolverError(f"AASA does not support {instance.variant!r}")
    if instance.depot != 0:
        raise SolverError("AASA requires the depot at index 0")
    if instance.capacity <= 0:
        raise SolverError("AASA requires a positive vehicle capacity")

    customers = list(instance.customers)
    if not customers:
        empty = Instance(
            name=f"{instance.name}-aasa",
            variant=CVRP,
            num_nodes=1,
            coords=instance.coords[[instance.depot]].copy(),
            demands=np.array([0], dtype=int),
            capacity=instance.capacity,
            distance=instance.distance[np.ix_([instance.depot], [instance.depot])].copy(),
            depot=0,
            max_vehicles=1,
        )
        return AASATransformation(empty, (instance.depot,), (0,))

    demands = [int(instance.demands[customer]) for customer in customers]
    if any(demand <= 0 for demand in demands):
        raise SolverError("AASA requires every customer demand to be positive")
    if any(demand > instance.capacity for demand in demands):
        raise SolverError("AASA requires every customer demand to be at most capacity")

    divisor = reduce(math.gcd, [int(instance.capacity), *demands])
    mu = sum(demand / divisor for demand in demands) / len(demands)
    smax = max(0, math.ceil(math.log(mu, 2)))
    max_depot_distance = max(
        float(instance.distance[instance.depot, customer]) for customer in customers
    )
    ring_boundary = max_depot_distance / 2.0

    parents = [instance.depot]
    quantities = [0]
    for customer, demand in zip(customers, demands):
        # The paper's prose and worked example assign the outer ring the coarser
        # level-1 denominations, despite Equation (5)'s reversed ring numbering.
        level = 1 if instance.distance[instance.depot, customer] > ring_boundary else 2
        max_exponent = max(0, smax - level + 1)
        denominations = [divisor * 2**exponent for exponent in range(max_exponent + 1)]
        remainder = demand
        for denomination in reversed(denominations):
            count, remainder = divmod(remainder, denomination)
            parents.extend([customer] * count)
            quantities.extend([denomination] * count)
        if remainder:
            raise SolverError(
                f"AASA could not decompose demand {demand} for customer {customer}"
            )

    parent_array = np.asarray(parents, dtype=int)
    fragment_array = np.asarray(quantities, dtype=int)
    transformed = Instance(
        name=f"{instance.name}-aasa-p2-l2",
        variant=CVRP,
        num_nodes=len(parents),
        coords=instance.coords[parent_array].copy(),
        demands=fragment_array,
        capacity=int(instance.capacity),
        distance=instance.distance[np.ix_(parent_array, parent_array)].copy(),
        depot=0,
        max_vehicles=_ffd_vehicle_bound(quantities[1:], int(instance.capacity)),
    )
    return AASATransformation(transformed, tuple(parents), tuple(quantities))


def decode_aasa(
    original: Instance,
    transformation: AASATransformation,
    base_solution: Solution,
    *,
    runtime_s: float,
) -> Solution:
    """Decode one CVRP solution, aggregating colocated clones per route."""
    virtual_count = transformation.instance.num_nodes
    seen: set[int] = set()
    routes: list[list[int]] = []
    deliveries: list[dict[int, int]] = []

    for base_route in base_solution.routes:
        route: list[int] = []
        delivered: dict[int, int] = {}
        for node in base_route:
            if not isinstance(node, (int, np.integer)) or not (1 <= int(node) < virtual_count):
                raise SolverError(f"AASA base solution contains invalid virtual node {node!r}")
            node = int(node)
            if node in seen:
                raise SolverError(f"AASA base solution contains repeated virtual customer {node}")
            seen.add(node)
            parent = transformation.parents[node]
            quantity = transformation.quantities[node]
            if parent not in delivered:
                route.append(parent)
                delivered[parent] = 0
            delivered[parent] += quantity
        if route:
            routes.append(route)
            deliveries.append(delivered)

    expected = set(range(1, virtual_count))
    missing = sorted(expected - seen)
    if missing:
        raise SolverError(f"AASA base solution is missing virtual customers: {missing}")

    objective = float(sum(route_distance(original, route) for route in routes))
    return Solution(
        routes=routes,
        objective=objective,
        feasible=base_solution.feasible,
        runtime_s=float(runtime_s),
        route_deliveries=deliveries,
    )


class AASASolver:
    """Use fixed-parameter AASA preprocessing with an existing CVRP solver."""

    supported_variants = (SDVRP,)

    def __init__(self, base_solver: Solver) -> None:
        if CVRP not in base_solver.supported_variants:
            raise SolverError("AASA requires a CVRP-capable base solver")
        self.base = base_solver
        self.name = f"aasa_{base_solver.name}"

    def version(self) -> str:
        return f"aasa-p2-l2+{self.base.version()}"

    def solve(self, instance: Instance, *, time_budget_s: float, seed: int) -> Solution:
        if instance.variant != SDVRP:
            raise SolverError(f"AASASolver does not support {instance.variant!r}")
        if time_budget_s <= 0:
            raise SolverError("AASA requires a positive time budget")

        start = time.perf_counter()
        transformation = transform_aasa(instance)
        remaining = float(time_budget_s) - (time.perf_counter() - start)
        if remaining <= 0:
            raise SolverError("AASA preprocessing exhausted the time budget")

        base_solution = self.base.solve(
            transformation.instance,
            time_budget_s=remaining,
            seed=seed,
        )
        runtime = time.perf_counter() - start
        return decode_aasa(
            instance,
            transformation,
            base_solution,
            runtime_s=runtime,
        )
