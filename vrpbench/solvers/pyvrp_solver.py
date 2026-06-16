"""PyVRP adapter — strong heuristic baseline for both CVRP and VRPTW.

The PyVRP ``ProblemData`` is built directly from our :class:`Instance`, using the
instance's authoritative distance matrix. PyVRP optimises over integers, so we
scale all quantities by a per-variant factor and round:

* CVRP  -> scale 1 (the distance matrix is already integer-valued).
* VRPTW -> scale 10 (the DIMACS convention; matches the 1-decimal Solomon/GH BKS).

PyVRP locations are [depot, clients...]; client visits map back to our customer
indices 1..n-1 directly. The objective is always re-scored against our matrix in
the evaluation layer; ``Solution.objective`` here is PyVRP's own (descaled) claim,
used only as a cross-check.
"""

from __future__ import annotations

import time

import numpy as np

from vrpbench.core.instance import CVRP, MDVRP, VRPTW, Instance
from vrpbench.core.solution import Solution
from vrpbench.solvers.base import SolverError, mdvrp_vehicles_per_depot

_SCALE = {CVRP: 1, VRPTW: 10, MDVRP: 1}


class PyVRPSolver:
    name = "pyvrp"
    supported_variants = (CVRP, VRPTW, MDVRP)

    def solve(self, instance: Instance, *, time_budget_s: float, seed: int) -> Solution:
        import pyvrp
        from pyvrp.stop import MaxRuntime

        if instance.variant not in _SCALE:
            raise SolverError(f"unsupported variant {instance.variant!r}")
        if instance.depot != 0:
            raise SolverError("PyVRP adapter assumes depot at index 0")
        scale = _SCALE[instance.variant]

        data = _build_data(pyvrp, instance, scale)

        start = time.perf_counter()
        result = pyvrp.solve(
            data, stop=MaxRuntime(time_budget_s), seed=seed, display=False
        )
        runtime_s = time.perf_counter() - start

        # PyVRP location indices match our node indices (depots first, then
        # clients in insertion order), so visits() are our customer indices and
        # start_depot() is our depot index.
        routes: list[list[int]] = []
        route_depots: list[int] = []
        for r in result.best.routes():
            visits = list(r.visits())
            if not visits:
                continue
            routes.append(visits)
            route_depots.append(int(r.start_depot()))

        return Solution(
            routes=routes,
            objective=result.cost() / scale,
            feasible=result.is_feasible(),
            runtime_s=runtime_s,
            route_depots=route_depots if instance.variant == MDVRP else [],
        )

    def version(self) -> str:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("pyvrp")
        except PackageNotFoundError:  # pragma: no cover
            return "unknown"


def _build_data(pyvrp, instance: Instance, scale: int):
    """Construct a PyVRP ProblemData from our unified Instance."""
    n = instance.num_nodes
    depot = instance.depot
    coords = instance.coords
    demands = instance.demands

    dist_int = np.rint(instance.distance * scale).astype(np.int64)

    if instance.variant == MDVRP:
        return _build_mdvrp_data(pyvrp, instance, dist_int)

    if instance.variant == VRPTW:
        tw = instance.time_windows
        service = instance.service_times
        assert tw is not None and service is not None
        tw_int = np.rint(tw * scale).astype(np.int64)
        svc_int = np.rint(service * scale).astype(np.int64)
        duration_int = dist_int  # travel time == distance for Solomon/GH
        depot_obj = pyvrp.Depot(
            x=float(coords[depot, 0]),
            y=float(coords[depot, 1]),
            tw_early=int(tw_int[depot, 0]),
            tw_late=int(tw_int[depot, 1]),
        )
        clients = [
            pyvrp.Client(
                x=float(coords[i, 0]),
                y=float(coords[i, 1]),
                delivery=[int(demands[i])],
                service_duration=int(svc_int[i]),
                tw_early=int(tw_int[i, 0]),
                tw_late=int(tw_int[i, 1]),
            )
            for i in range(n)
            if i != depot
        ]
        vehicle_tw = (int(tw_int[depot, 0]), int(tw_int[depot, 1]))
    else:  # CVRP
        duration_int = np.zeros((n, n), dtype=np.int64)
        depot_obj = pyvrp.Depot(x=float(coords[depot, 0]), y=float(coords[depot, 1]))
        clients = [
            pyvrp.Client(
                x=float(coords[i, 0]),
                y=float(coords[i, 1]),
                delivery=[int(demands[i])],
            )
            for i in range(n)
            if i != depot
        ]
        vehicle_tw = None

    # Generous fleet: one vehicle per customer is a safe feasibility upper bound;
    # the objective (distance) drives PyVRP to use as few as it needs.
    num_vehicles = max(1, n - 1)
    vt_kwargs = dict(num_available=num_vehicles, capacity=[int(instance.capacity)])
    if vehicle_tw is not None:
        vt_kwargs.update(tw_early=vehicle_tw[0], tw_late=vehicle_tw[1])
    vehicle_type = pyvrp.VehicleType(**vt_kwargs)

    # ProblemData expects the depot at index 0; our instances already use depot 0,
    # and clients are emitted in ascending index order, preserving the mapping.
    return pyvrp.ProblemData(
        clients=clients,
        depots=[depot_obj],
        vehicle_types=[vehicle_type],
        distance_matrices=[dist_int],
        duration_matrices=[duration_int],
    )


def _build_mdvrp_data(pyvrp, instance: Instance, dist_int):
    """MDVRP ProblemData: one Depot per depot index, one VehicleType per depot.

    Depots occupy location indices ``0..t-1`` and clients follow at ``t..n-1`` in
    insertion order, exactly matching our node indexing — so the distance matrix is
    used as-is and ``Route.visits()`` / ``Route.start_depot()`` map straight back.
    Open depot assignment is PyVRP's default: a client may be served by any vehicle
    type, so the search chooses the depot for each customer.
    """
    n = instance.num_nodes
    coords = instance.coords
    demands = instance.demands
    depot_indices = instance.depot_indices

    depots = [
        pyvrp.Depot(x=float(coords[d, 0]), y=float(coords[d, 1])) for d in depot_indices
    ]
    clients = [
        pyvrp.Client(
            x=float(coords[i, 0]),
            y=float(coords[i, 1]),
            delivery=[int(demands[i])],
        )
        for i in instance.customers
    ]

    # Generous-but-bounded per-depot fleet (see mdvrp_vehicles_per_depot); the
    # distance objective drives PyVRP to use as few as it needs.
    num_per_depot = mdvrp_vehicles_per_depot(instance)
    vehicle_types = [
        pyvrp.VehicleType(
            num_available=num_per_depot,
            capacity=[int(instance.capacity)],
            start_depot=d,
            end_depot=d,
        )
        for d in range(len(depot_indices))
    ]

    duration_int = np.zeros((n, n), dtype=np.int64)
    return pyvrp.ProblemData(
        clients=clients,
        depots=depots,
        vehicle_types=vehicle_types,
        distance_matrices=[dist_int],
        duration_matrices=[duration_int],
    )
