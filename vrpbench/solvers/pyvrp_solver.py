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

from vrpbench.core.instance import CVRP, VRPTW, Instance
from vrpbench.core.solution import Solution
from vrpbench.solvers.base import SolverError

_SCALE = {CVRP: 1, VRPTW: 10}


class PyVRPSolver:
    name = "pyvrp"
    supported_variants = (CVRP, VRPTW)

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

        routes = [list(r.visits()) for r in result.best.routes() if len(r.visits()) > 0]

        return Solution(
            routes=routes,
            objective=result.cost() / scale,
            feasible=result.is_feasible(),
            runtime_s=runtime_s,
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
