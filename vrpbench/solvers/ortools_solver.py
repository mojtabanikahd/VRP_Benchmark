"""OR-Tools adapter — baseline solver for CVRP and VRPTW.

The routing model is built from the instance's authoritative distance matrix.
CVRP uses the integer matrix directly (scale 1); VRPTW scales distances, travel
times, time windows and service times by 10 (DIMACS convention, matching the
PyVRP adapter and the 1-decimal Solomon/GH BKS). The reported objective is
descaled; the evaluation layer always re-scores against our matrix.

OR-Tools' classic routing search exposes no RNG seed; results are effectively
deterministic given fixed parameters. The ``seed`` argument is accepted (and
recorded by the runner) but does not alter OR-Tools' search.
"""

from __future__ import annotations

import math
import time

import numpy as np

from vrpbench.core.instance import CVRP, MDVRP, VRPTW, Instance
from vrpbench.core.solution import Solution
from vrpbench.solvers.base import SolverError, mdvrp_vehicles_per_depot

_SCALE = {CVRP: 1, VRPTW: 10, MDVRP: 1}


class OrToolsSolver:
    name = "ortools"
    supported_variants = (CVRP, VRPTW, MDVRP)

    def solve(self, instance: Instance, *, time_budget_s: float, seed: int) -> Solution:
        from ortools.constraint_solver import pywrapcp, routing_enums_pb2

        if instance.variant not in _SCALE:
            raise SolverError(f"OrToolsSolver does not support {instance.variant!r}")
        scale = _SCALE[instance.variant]

        n = instance.num_nodes
        depot = instance.depot
        dist = np.rint(instance.distance * scale).astype(np.int64)
        demands = instance.demands.astype(np.int64)

        if instance.variant == MDVRP:
            # One block of vehicles per depot, each fixed to start and end at its
            # depot (native multi-depot). A generous per-depot fleet (one vehicle
            # per customer) guarantees a feasible assignment exists regardless of
            # how the search distributes customers across depots.
            depot_indices = instance.depot_indices
            vehicles_per_depot = mdvrp_vehicles_per_depot(instance)
            starts = [d for d in depot_indices for _ in range(vehicles_per_depot)]
            ends = list(starts)
            num_vehicles = len(starts)
            manager = pywrapcp.RoutingIndexManager(n, num_vehicles, starts, ends)
        else:
            num_vehicles = _vehicle_count(instance)
            manager = pywrapcp.RoutingIndexManager(n, num_vehicles, depot)
        routing = pywrapcp.RoutingModel(manager)

        def distance_cb(from_index: int, to_index: int) -> int:
            return int(dist[manager.IndexToNode(from_index), manager.IndexToNode(to_index)])

        transit_idx = routing.RegisterTransitCallback(distance_cb)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

        def demand_cb(from_index: int) -> int:
            return int(demands[manager.IndexToNode(from_index)])

        demand_idx = routing.RegisterUnaryTransitCallback(demand_cb)
        routing.AddDimensionWithVehicleCapacity(
            demand_idx, 0, [int(instance.capacity)] * num_vehicles, True, "Capacity"
        )

        if instance.variant == VRPTW:
            _add_time_windows(
                routing, manager, instance, dist, scale, num_vehicles
            )

        params = pywrapcp.DefaultRoutingSearchParameters()
        params.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        params.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        params.time_limit.FromMilliseconds(max(1, int(time_budget_s * 1000)))
        params.log_search = False

        start = time.perf_counter()
        solution = routing.SolveWithParameters(params)
        runtime_s = time.perf_counter() - start

        if solution is None:
            raise SolverError("OR-Tools found no solution within the time budget")

        routes, route_depots = _extract_routes(routing, manager, solution, num_vehicles)
        return Solution(
            routes=routes,
            objective=float(solution.ObjectiveValue()) / scale,
            feasible=True,  # re-verified independently by the evaluation layer
            runtime_s=runtime_s,
            route_depots=route_depots if instance.variant == MDVRP else [],
        )

    def version(self) -> str:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("ortools")
        except PackageNotFoundError:  # pragma: no cover
            return "unknown"


def _add_time_windows(routing, manager, instance, dist, scale, num_vehicles) -> None:
    """Add a Time dimension: transit = travel time + service time at origin."""
    tw = instance.time_windows
    service = instance.service_times
    assert tw is not None and service is not None
    tw_int = np.rint(tw * scale).astype(np.int64)
    svc_int = np.rint(service * scale).astype(np.int64)
    depot = instance.depot

    def time_cb(from_index: int, to_index: int) -> int:
        i = manager.IndexToNode(from_index)
        j = manager.IndexToNode(to_index)
        return int(dist[i, j] + svc_int[i])

    time_idx = routing.RegisterTransitCallback(time_cb)
    horizon = int(tw_int[:, 1].max() + svc_int.sum() + 1)
    # Large slack permits waiting until a customer's window opens.
    routing.AddDimension(time_idx, horizon, horizon, False, "Time")
    time_dim = routing.GetDimensionOrDie("Time")

    for node in range(instance.num_nodes):
        if node == depot:
            continue
        index = manager.NodeToIndex(node)
        time_dim.CumulVar(index).SetRange(int(tw_int[node, 0]), int(tw_int[node, 1]))

    depot_open, depot_close = int(tw_int[depot, 0]), int(tw_int[depot, 1])
    for v in range(num_vehicles):
        time_dim.CumulVar(routing.Start(v)).SetRange(depot_open, depot_close)
        time_dim.CumulVar(routing.End(v)).SetRange(depot_open, depot_close)


def _vehicle_count(instance: Instance) -> int:
    """Enough vehicles to guarantee a feasible solution exists."""
    min_by_capacity = math.ceil(int(instance.demands.sum()) / instance.capacity)
    declared = instance.num_vehicles or 0
    return max(1, declared, min_by_capacity)


def _extract_routes(
    routing, manager, solution, num_vehicles
) -> tuple[list[list[int]], list[int]]:
    """Return (routes, route_depots); route_depots[i] is route i's start node."""
    routes: list[list[int]] = []
    route_depots: list[int] = []
    for v in range(num_vehicles):
        index = routing.Start(v)
        depot_node = manager.IndexToNode(index)
        route: list[int] = []
        while not routing.IsEnd(index):
            if not routing.IsStart(index):
                route.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
        if route:
            routes.append(route)
            route_depots.append(depot_node)
    return routes, route_depots
