"""VRPSolverEasy adapter (exact Branch-Cut-and-Price solver via BaPCod).

Translates a unified :class:`Instance` into a VRPSolverEasy ``Model``, runs the
exact solver VRPSolver under a wall-clock time budget, and converts the result
back into our :class:`Solution`. Both CVRP and VRPTW are supported.

Design decisions (confirmed against VRPSolverEasy 0.1.4, VRPSolver v0.6.9,
BaPCod v0.82.4; see CLAUDE.md and BAPCOD_SETUP.md):

* Scaling mirrors the other adapters — CVRP scale 1, VRPTW scale 10 (DIMACS) —
  so all solvers see byte-identical integer matrices and times.
* VRPSolverEasy uses a link-based graph API, not a matrix. We add one undirected
  link per node pair (O(n²) Python calls) with distance (cost) and time
  (for VRPTW time-window propagation). Time == distance (Solomon/GH convention).
* Time budget is honored via ``set_parameters(time_limit=time_budget_s)``. The
  solver returns the best feasible solution found within the budget; if none is
  found, solution is undefined (status will be 3, "time limit exceeded"). ``seed``
  is accepted but ignored — BCP with CLP is deterministic for a fixed budget.
* Customer/depot IDs map directly to location indices. Route extraction must
  filter out all depot occurrences (point_ids includes [0, ..., 0]).
* **Critical:** Even CVRP must supply an open time window [0, HORIZON] on every
  entity (vehicle type, depot, customers). Omitting windows defaults them to
  [0, 0], making the model infeasible. HORIZON = sum of all scaled distances.
* Hard point limit: VRPSolver max is 1022 nodes (including depot). Guard with
  SolverError for larger instances.
* BaPCod binaries (bapcod-shared.dll etc.) must be present in the package
  lib/<OS> directory; the pip wheel does not include them. See BAPCOD_SETUP.md.
"""

from __future__ import annotations

import time

import numpy as np

from vrpbench.core.instance import CVRP, VRPTW, Instance
from vrpbench.core.solution import Solution
from vrpbench.solvers.base import SolverError

_SCALE = {CVRP: 1, VRPTW: 10}
_MAX_NODES = 1022


class VRPSolverEasySolver:
    name = "vrpsolvereasy"
    supported_variants = (CVRP, VRPTW)

    def __init__(
        self, solver_name: str = "CLP", heuristic_used: bool = False, print_level: int = -2
    ) -> None:
        """Engine knobs (kept off ``solve``'s signature to stay interchangeable).

        Args:
            solver_name: MIP solver to use ("CLP" for free version, "CPLEX" for academic).
            heuristic_used: Whether to use a heuristic to find feasible solutions
                before exact solve (academic version with CPLEX only).
            print_level: Verbosity (-2, -1, or 0; -2 suppresses all output).
        """
        self.solver_name = solver_name
        self.heuristic_used = heuristic_used
        self.print_level = print_level

    def solve(self, instance: Instance, *, time_budget_s: float, seed: int) -> Solution:
        """Solve ``instance`` within ``time_budget_s`` seconds; ``seed`` is ignored.

        The exact BCP solver (VRPSolver/BaPCod) runs until optimality is proven
        or the time budget expires. If no feasible solution is found within the
        budget, returns infeasible. The solver is deterministic for a fixed budget
        (no seed effect), matching the OR-Tools/VROOM convention.
        """
        if instance.variant not in _SCALE:
            raise SolverError(f"VRPSolverEasySolver does not support {instance.variant!r}")

        if instance.num_nodes > _MAX_NODES:
            raise SolverError(
                f"VRPSolver hard limit is {_MAX_NODES} nodes; "
                f"instance has {instance.num_nodes}"
            )

        scale = _SCALE[instance.variant]
        model = _build_model(instance, scale)

        model.set_parameters(
            time_limit=time_budget_s,
            solver_name=self.solver_name,
            heuristic_used=self.heuristic_used,
            print_level=self.print_level,
        )

        start = time.perf_counter()
        try:
            model.solve()
        except Exception as exc:
            raise SolverError(
                f"VRPSolverEasy solve failed: {exc}. "
                f"Ensure BaPCod binaries are installed per BAPCOD_SETUP.md"
            ) from exc
        runtime_s = time.perf_counter() - start

        return _to_solution(model, instance, scale, runtime_s)

    def version(self) -> str:
        """Return the VRPSolverEasy package version (recorded for reproducibility)."""
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("VRPSolverEasy")
        except PackageNotFoundError:  # pragma: no cover
            return "unknown"


def _to_solution(
    model, instance: Instance, scale: int, runtime_s: float
) -> Solution:
    """Convert a VRPSolver solution into our canonical :class:`Solution`.

    If no feasible solution was found (model.solution.is_defined() == False),
    return an infeasible solution with empty routes. Otherwise, extract routes by
    filtering depot nodes (point_ids includes [0, ..., 0]) and descale the
    objective (model.solution.value carries float noise; evaluation re-scores).
    """
    if not model.solution.is_defined():
        return Solution(
            routes=[],
            objective=0.0,
            feasible=False,
            runtime_s=runtime_s,
        )

    routes: list[list[int]] = []
    for route in model.solution.routes:
        # point_ids includes depot at both ends; filter all depot occurrences
        customer_route = [int(p) for p in route.point_ids if p != instance.depot]
        if customer_route:
            routes.append(customer_route)

    return Solution(
        routes=routes,
        objective=float(model.solution.value) / scale,
        feasible=True,
        runtime_s=runtime_s,
    )


def _build_model(instance: Instance, scale: int):
    """Translate an :class:`Instance` into a VRPSolverEasy ``Model`` (CVRP or VRPTW).

    VRPSolverEasy uses a link-based graph: we add one undirected link per node pair
    with the scaled integer distance as both cost and travel time. Even CVRP must
    supply an open time window [0, HORIZON] on every entity to avoid the [0,0]
    infeasibility trap (confirmed empirically). HORIZON is the sum of all scaled
    distances, a guaranteed upper bound on any single route's travel time.
    """
    from VRPSolverEasy.src import solver

    n = instance.num_nodes
    depot = instance.depot
    demands = instance.demands

    # Scaled, rounded distance matrix
    dist_int = np.rint(instance.distance * scale).astype(np.int64)

    # HORIZON = sum of all distances, safe upper bound for any route
    horizon = int(dist_int.sum())

    model = solver.Model()

    is_vrptw = instance.variant == VRPTW
    if is_vrptw:
        tw = instance.time_windows
        service = instance.service_times
        assert tw is not None and service is not None  # guaranteed for VRPTW
        tw_int = np.rint(tw * scale).astype(np.int64)
        svc_int = np.rint(service * scale).astype(np.int64)
        depot_tw_begin = int(tw_int[depot, 0])
        depot_tw_end = int(tw_int[depot, 1])
    else:
        depot_tw_begin = 0
        depot_tw_end = horizon

    # Add vehicle type (homogeneous fleet)
    num_vehicles = max(1, n - 1)
    model.add_vehicle_type(
        id=1,
        start_point_id=depot,
        end_point_id=depot,
        max_number=num_vehicles,
        capacity=int(instance.capacity),
        var_cost_dist=1,
        tw_begin=0,
        tw_end=horizon,
    )

    # Add depot
    model.add_depot(
        id=depot,
        service_time=0,
        tw_begin=depot_tw_begin,
        tw_end=depot_tw_end,
    )

    # Add customers
    for i in range(n):
        if i == depot:
            continue
        if is_vrptw:
            cust_tw_begin = int(tw_int[i, 0])
            cust_tw_end = int(tw_int[i, 1])
            cust_service = int(svc_int[i])
        else:
            cust_tw_begin = 0
            cust_tw_end = horizon
            cust_service = 0

        model.add_customer(
            id=i,
            demand=int(demands[i]),
            service_time=cust_service,
            tw_begin=cust_tw_begin,
            tw_end=cust_tw_end,
        )

    # Add links (undirected, symmetric matrix)
    for i in range(n):
        for j in range(i + 1, n):
            dist = int(dist_int[i, j])
            model.add_link(
                start_point_id=i,
                end_point_id=j,
                distance=dist,
                time=dist,
                is_directed=False,
            )

    return model
