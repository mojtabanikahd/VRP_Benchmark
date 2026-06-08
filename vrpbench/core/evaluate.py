"""Independent evaluation of VRP solutions.

The solver's reported objective and feasibility are never trusted blindly:
``verify`` recomputes the objective from the instance's authoritative distance
matrix and independently checks all constraints.
"""

from __future__ import annotations

from dataclasses import dataclass

from vrpbench.core.instance import VRPTW, Instance
from vrpbench.core.solution import Solution

# Tolerance for comparing solver-reported vs recomputed objective.
OBJ_EPS = 1e-4


@dataclass(frozen=True)
class Evaluation:
    objective: float  # recomputed total distance
    feasible: bool  # independently verified
    num_vehicles: int  # number of non-empty routes
    violations: list[str]  # human-readable list of constraint violations
    obj_mismatch: float  # |recomputed - solver_reported|


def route_distance(instance: Instance, route: list[int]) -> float:
    """Distance of a single route, depot -> customers -> depot."""
    if not route:
        return 0.0
    d = instance.distance
    depot = instance.depot
    total = d[depot, route[0]]
    for a, b in zip(route, route[1:]):
        total += d[a, b]
    total += d[route[-1], depot]
    return float(total)


def total_distance(instance: Instance, solution: Solution) -> float:
    return sum(route_distance(instance, r) for r in solution.routes)


def verify(instance: Instance, solution: Solution) -> Evaluation:
    """Recompute the objective and check all constraints independently."""
    violations: list[str] = []

    # --- visiting constraints -------------------------------------------------
    visited: list[int] = [c for r in solution.routes for c in r]
    expected = set(instance.customers)
    seen = set(visited)

    if len(visited) != len(seen):
        dupes = sorted({c for c in visited if visited.count(c) > 1})
        violations.append(f"duplicate customers visited: {dupes}")
    missing = sorted(expected - seen)
    if missing:
        violations.append(f"unvisited customers: {missing}")
    extra = sorted(seen - expected)
    if extra:
        violations.append(f"invalid node indices in routes: {extra}")
    if instance.depot in seen:
        violations.append("depot appears inside a route")

    # --- capacity -------------------------------------------------------------
    for i, route in enumerate(solution.routes):
        load = int(sum(instance.demands[c] for c in route if 0 <= c < instance.num_nodes))
        if load > instance.capacity:
            violations.append(
                f"route {i} load {load} exceeds capacity {instance.capacity}"
            )

    # --- time windows (VRPTW only) -------------------------------------------
    if instance.variant == VRPTW:
        violations.extend(_check_time_windows(instance, solution))

    # --- objective ------------------------------------------------------------
    objective = total_distance(instance, solution)
    obj_mismatch = abs(objective - solution.objective)

    num_vehicles = sum(1 for r in solution.routes if r)
    feasible = not violations

    return Evaluation(
        objective=objective,
        feasible=feasible,
        num_vehicles=num_vehicles,
        violations=violations,
        obj_mismatch=obj_mismatch,
    )


def _check_time_windows(instance: Instance, solution: Solution) -> list[str]:
    """Simulate each route; waiting before earliest is allowed, lateness is not."""
    violations: list[str] = []
    d = instance.distance
    depot = instance.depot
    tw = instance.time_windows
    service = instance.service_times
    assert tw is not None and service is not None  # guaranteed for VRPTW

    for i, route in enumerate(solution.routes):
        if not route:
            continue
        # Depart depot at its earliest opening time.
        t = float(tw[depot, 0])
        prev = depot
        for c in route:
            t += d[prev, c]
            if t > tw[c, 1] + OBJ_EPS:
                violations.append(
                    f"route {i}: customer {c} arrival {t:.3f} > latest {tw[c, 1]:.3f}"
                )
                break
            t = max(t, float(tw[c, 0]))  # wait until window opens
            t += float(service[c])
            prev = c
        else:
            # Return to depot must respect the depot's closing time.
            t += d[prev, depot]
            if t > tw[depot, 1] + OBJ_EPS:
                violations.append(
                    f"route {i}: return {t:.3f} > depot close {tw[depot, 1]:.3f}"
                )
    return violations


def gap(objective: float, bks: float | None) -> float | None:
    """Percentage gap to the best-known solution; None if BKS unknown."""
    if bks is None or bks <= 0:
        return None
    return 100.0 * (objective - bks) / bks
