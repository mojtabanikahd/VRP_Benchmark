"""Independent evaluation of VRP solutions.

The solver's reported objective and feasibility are never trusted blindly:
``verify`` recomputes the objective from the instance's authoritative distance
matrix and independently checks all constraints.
"""

from __future__ import annotations

from dataclasses import dataclass

from vrpbench.core.instance import MDVRP, VRPMPD, VRPTW, Instance
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


def route_distance(instance: Instance, route: list[int], depot: int | None = None) -> float:
    """Distance of a single route, depot -> customers -> depot.

    ``depot`` defaults to ``instance.depot`` (single-depot CVRP/VRPTW). For MDVRP,
    pass the route's assigned depot so the first/last legs are anchored correctly.
    """
    if not route:
        return 0.0
    d = instance.distance
    if depot is None:
        depot = instance.depot
    total = d[depot, route[0]]
    for a, b in zip(route, route[1:]):
        total += d[a, b]
    total += d[route[-1], depot]
    return float(total)


def total_distance(instance: Instance, solution: Solution) -> float:
    # MDVRP: anchor each route at its own depot when that mapping is available.
    # An out-of-range depot (a buggy solution, separately flagged by verify) falls
    # back to the primary depot so the recompute stays finite instead of crashing.
    if instance.variant == MDVRP and len(solution.route_depots) == len(solution.routes):
        depots = set(instance.depot_indices or ())
        return sum(
            route_distance(instance, r, d if d in depots else instance.depot)
            for r, d in zip(solution.routes, solution.route_depots)
        )
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
    depots = set(instance.depot_indices) if instance.depot_indices else {instance.depot}
    if seen & depots:
        violations.append("depot appears inside a route")

    # --- capacity -------------------------------------------------------------
    if instance.variant == VRPMPD:
        violations.extend(_check_vrpmpd_capacity(instance, solution))
    else:
        for i, route in enumerate(solution.routes):
            load = int(sum(instance.demands[c] for c in route if 0 <= c < instance.num_nodes))
            if load > instance.capacity:
                violations.append(
                    f"route {i} load {load} exceeds capacity {instance.capacity}"
                )

    # --- multi-depot route assignment (MDVRP only) ---------------------------
    if instance.variant == MDVRP:
        violations.extend(_check_route_depots(instance, solution))

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


def _check_route_depots(instance: Instance, solution: Solution) -> list[str]:
    """MDVRP: every route must name exactly one valid depot it starts/ends at."""
    violations: list[str] = []
    depots = set(instance.depot_indices or ())
    rd = solution.route_depots
    if len(rd) != len(solution.routes):
        violations.append(
            f"route_depots length {len(rd)} does not match {len(solution.routes)} routes"
        )
        return violations
    bad = sorted({d for d in rd if d not in depots})
    if bad:
        violations.append(f"routes assigned to invalid depots: {bad}")
    return violations


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


def _check_vrpmpd_capacity(instance: Instance, solution: Solution) -> list[str]:
    """Position-dependent capacity check for VRPMPD.

    A vehicle departs the depot loaded with all of its route's deliveries; at each
    stop the load drops by the delivery amount and rises by the pickup amount.  The
    capacity must not be exceeded (or go negative) at any point along the route.
    """
    violations: list[str] = []
    cap = instance.capacity
    deliveries = instance.deliveries
    pickups = instance.pickups
    assert deliveries is not None and pickups is not None  # guaranteed for VRPMPD

    for i, route in enumerate(solution.routes):
        if not route:
            continue
        # Initial load = sum of all deliveries on this route (vehicle leaves full).
        load = int(sum(deliveries[c] for c in route if 0 <= c < instance.num_nodes))
        if load > cap:
            violations.append(
                f"route {i}: departure load {load} exceeds capacity {cap}"
            )
            continue
        for c in route:
            if not (0 <= c < instance.num_nodes):
                continue
            load -= int(deliveries[c])
            load += int(pickups[c])
            if load > cap:
                violations.append(
                    f"route {i}: load {load} after customer {c} exceeds capacity {cap}"
                )
                break
            if load < 0:
                violations.append(
                    f"route {i}: load {load} after customer {c} is negative"
                )
                break
    return violations


def gap(objective: float, bks: float | None) -> float | None:
    """Percentage gap to the best-known solution; None if BKS unknown."""
    if bks is None or bks <= 0:
        return None
    return 100.0 * (objective - bks) / bks
