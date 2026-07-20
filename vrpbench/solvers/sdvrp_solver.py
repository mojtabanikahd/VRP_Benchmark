"""SDVRP R1 adapter for homogeneous split-delivery VRP instances.

The DIMACS R1 SDVRP benchmark is the canonical split-delivery relaxation of
CVRP: homogeneous capacity, no site-dependent vehicle types, no route-duration
limits, and no hard fleet cap in the input.  The wrapper keeps the historical
registry names (``sdvrp_tabu``, ``sdvrp_pyvrp``, ``sdvrp_ortools``,
``sdvrp_vroom``) while producing explicit per-route delivery maps for the
evaluator and detail JSON.
"""

from __future__ import annotations

import time

from vrpbench.core.evaluate import route_distance
from vrpbench.core.instance import CVRP, SDVRP, Instance
from vrpbench.core.solution import Solution
from vrpbench.solvers.base import Solver, SolverError


class SDVRPSolver:
    """Homogeneous SDVRP wrapper, optionally seeded by a CVRP base solver."""

    supported_variants = (SDVRP,)

    def __init__(self, base_solver: Solver | None = None) -> None:
        self.base = base_solver
        self.name = "sdvrp_tabu" if base_solver is None else f"sdvrp_{base_solver.name}"

    def version(self) -> str:
        if self.base is None:
            return "sdvrp-tabu-r1"
        return f"sdvrp-r1+{self.base.version()}"

    def solve(self, instance: Instance, *, time_budget_s: float, seed: int) -> Solution:
        if instance.variant != SDVRP:
            raise SolverError(f"SDVRPSolver does not support {instance.variant!r}")
        if instance.depot != 0:
            raise SolverError("SDVRPSolver assumes depot at index 0")

        start = time.perf_counter()
        if not list(instance.customers):
            return Solution(routes=[], objective=0.0, feasible=True, runtime_s=0.0)

        routes = self._initial_routes(instance, time_budget_s=time_budget_s, seed=seed)
        routes = _pack_routes(instance, routes)
        deliveries = [{c: int(instance.demands[c]) for c in route} for route in routes]
        objective = float(sum(route_distance(instance, route) for route in routes))

        return Solution(
            routes=routes,
            objective=objective,
            feasible=True,
            runtime_s=time.perf_counter() - start,
            route_deliveries=deliveries,
        )

    def _initial_routes(self, instance: Instance, *, time_budget_s: float, seed: int) -> list[list[int]]:
        if self.base is None:
            return _greedy_routes(instance)
        relaxed = Instance(
            name=f"{instance.name}-relaxed",
            variant=CVRP,
            num_nodes=instance.num_nodes,
            coords=instance.coords,
            demands=instance.demands,
            capacity=instance.capacity,
            distance=instance.distance,
            depot=instance.depot,
            num_vehicles=None,
            max_vehicles=_route_slot_bound(instance),
        )
        try:
            init_budget = float(min(15.0, max(1.0, time_budget_s * 0.3)))
            sol = self.base.solve(relaxed, time_budget_s=init_budget, seed=seed)
        except SolverError:
            return _greedy_routes(instance)
        routes = [[c for c in route if c in set(instance.customers)] for route in sol.routes]
        seen = {c for route in routes for c in route}
        routes.extend([[c] for c in instance.customers if c not in seen])
        return [route for route in routes if route]


def _route_slot_bound(instance: Instance) -> int:
    """Internal search bound only; SDVRP R1 has no semantic fleet cap."""
    total = int(sum(instance.demands[c] for c in instance.customers))
    return max(1, sum(_ceil_div(int(instance.demands[c]), instance.capacity) for c in instance.customers), _ceil_div(total, instance.capacity))


def _ceil_div(a: int, b: int) -> int:
    return -(-a // b)


def _greedy_routes(instance: Instance) -> list[list[int]]:
    routes: list[list[int]] = []
    current: list[int] = []
    load = 0
    for c in sorted(instance.customers, key=lambda x: -int(instance.demands[x])):
        demand = int(instance.demands[c])
        if current and load + demand > instance.capacity:
            routes.append(current)
            current = []
            load = 0
        current.append(c)
        load += demand
    if current:
        routes.append(current)
    return routes


def _pack_routes(instance: Instance, seed_routes: list[list[int]]) -> list[list[int]]:
    """First-fit pack a seed order into homogeneous capacity routes."""
    order: list[int] = []
    seen: set[int] = set()
    for route in seed_routes:
        for c in route:
            if c in seen or c not in set(instance.customers):
                continue
            seen.add(c)
            order.append(c)
    order.extend(c for c in instance.customers if c not in seen)

    routes: list[list[int]] = []
    loads: list[int] = []
    for c in order:
        demand = int(instance.demands[c])
        placed = False
        for idx, load in enumerate(loads):
            if load + demand <= instance.capacity:
                routes[idx].append(c)
                loads[idx] += demand
                placed = True
                break
        if not placed:
            routes.append([c])
            loads.append(demand)
    return routes
