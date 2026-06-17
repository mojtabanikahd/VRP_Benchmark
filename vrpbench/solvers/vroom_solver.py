"""VROOM adapter (via ``pyvroom``) — fast open-source heuristic for CVRP and VRPTW.

Translates a unified :class:`Instance` into a ``vroom.Input``, runs VROOM under a
wall-clock budget, and converts the result back into our :class:`Solution`. CVRP
is fully wired; VRPTW (service times / time windows) is added in Step 6.

Design decisions (confirmed against pyvroom 1.15.2; see CLAUDE.md and
PYVROOM_COMPATIBILITY_ISSUE.md):

* Scaling mirrors the other adapters — CVRP scale 1, VRPTW scale 10 (DIMACS) —
  so all three solvers see byte-identical integer matrices. The distance matrix
  is fed as VROOM's duration matrix, serving as both the cost objective and (for
  VRPTW) the travel-time basis (travel time == distance for Solomon/GH).
* Time budget is honored via ``Input.solve(timeout=timedelta(seconds=...))`` with
  a fixed ``exploration_level`` (an engine knob, hence a constructor default).
  ``seed`` is accepted but ignored — VROOM is deterministic at ``nb_threads=1``,
  mirroring how ``OrToolsSolver`` accepts but ignores ``seed``.
* Locations are indexed directly: each job's ``id`` and ``location`` are set to
  the customer index, so solution rows map back to our customer indices.
* Windows: the duration matrix must be wrapped as
  ``_vroom.Matrix(np.ascontiguousarray(M, dtype=np.uintc))`` to dodge pyvroom's
  internal ``uint32`` (buffer format ``'L'``) cast, which the C++ ``_vroom.Matrix``
  buffer (``'I'``) rejects. See PYVROOM_COMPATIBILITY_ISSUE.md.
"""

from __future__ import annotations

import time
from datetime import timedelta

import numpy as np

from vrpbench.core.instance import CVRP, MDVRP, VRPMPD, VRPTW, Instance
from vrpbench.core.solution import Solution
from vrpbench.solvers.base import (
    SolverError,
    lexicographic_fixed_cost,
    mdvrp_vehicles_per_depot,
    vrpmpd_max_vehicles,
)

_SCALE = {CVRP: 1, VRPTW: 10, MDVRP: 1, VRPMPD: 1}
_PROFILE = "car"


class VroomSolver:
    name = "vroom"
    supported_variants = (CVRP, VRPTW, MDVRP, VRPMPD)

    def __init__(self, exploration_level: int = 5, nb_threads: int = 1) -> None:
        """Engine knobs (kept off ``solve``'s signature to stay interchangeable).

        Args:
            exploration_level: VROOM search aggressiveness (1-5, default 5).
            nb_threads: Threads for the solve (default 1, for determinism).
        """
        self.exploration_level = exploration_level
        self.nb_threads = nb_threads

    def solve(self, instance: Instance, *, time_budget_s: float, seed: int) -> Solution:
        """Solve ``instance`` within ``time_budget_s`` seconds; ``seed`` is ignored.

        VROOM runs at the fixed ``exploration_level`` with the budget passed as a
        ``timeout``; ``seed`` has no effect (VROOM is deterministic at
        ``nb_threads=1``). The reported objective is VROOM's own (descaled) cost;
        the evaluation layer always re-scores against the instance matrix.
        """
        if instance.variant not in _SCALE:
            raise SolverError(f"VroomSolver does not support {instance.variant!r}")

        scale = _SCALE[instance.variant]
        problem, vehicle_depot = _build_input(instance, scale)

        start = time.perf_counter()
        try:
            result = problem.solve(
                exploration_level=self.exploration_level,
                nb_threads=self.nb_threads,
                timeout=timedelta(seconds=time_budget_s),
            )
        except RuntimeError as exc:  # VROOM signals bad input / search failure here
            raise SolverError(f"VROOM solve failed: {exc}") from exc
        runtime_s = time.perf_counter() - start

        return _to_solution(result, scale, runtime_s, vehicle_depot, instance.variant)

    def version(self) -> str:
        """Return the pyvroom package version (recorded for reproducibility)."""
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("pyvroom")
        except PackageNotFoundError:  # pragma: no cover
            return "unknown"


def _to_solution(
    result,
    scale: int,
    runtime_s: float,
    vehicle_depot: dict[int, int] | None = None,
    variant: str = "",
) -> Solution:
    """Convert a VROOM solution into our canonical :class:`Solution`.

    ``result.routes`` is a per-step ``pandas.DataFrame``; we group by
    ``vehicle_id``, keep ``type == "job"`` rows in order, and collect their ``id``
    (== our customer index) into one list per non-empty route. Any unassigned job
    marks the solution infeasible (the evaluator re-verifies).

    For MDVRP, ``vehicle_depot`` maps each vehicle id to its (fixed) depot node, so
    each non-empty route records the depot it starts and ends at.

    For VRPMPD the solver objective (``summary.cost``) includes the fixed vehicle
    cost; we report ``summary.duration`` instead, which equals pure travel distance
    because the distance matrix is fed as VROOM's duration matrix with service=0.
    """
    df = result.routes
    routes: list[list[int]] = []
    route_depots: list[int] = []
    for vehicle_id in df["vehicle_id"].unique():
        steps = df[df["vehicle_id"] == vehicle_id]
        route = [int(i) for i in steps.loc[steps["type"] == "job", "id"]]
        if route:
            routes.append(route)
            if vehicle_depot is not None:
                route_depots.append(int(vehicle_depot[int(vehicle_id)]))

    if variant == VRPMPD:
        objective = float(result.summary.duration) / scale
    else:
        objective = float(result.summary.cost) / scale

    return Solution(
        routes=routes,
        objective=objective,
        feasible=int(result.summary.unassigned) == 0,
        runtime_s=runtime_s,
        route_depots=route_depots if vehicle_depot is not None else [],
    )


def _vroom_matrix(matrix_int: np.ndarray):
    """Build a ``_vroom.Matrix`` from an integer matrix, Windows-safe.

    pyvroom's ``set_*_matrix`` hard-casts to numpy ``uint32`` (buffer format
    ``'L'`` on Windows/MSVC), which the C++ ``_vroom.Matrix`` buffer (``'I'``)
    rejects with ``Incompatible buffer format!``. Building the ``Matrix`` here from
    a ``np.uintc`` (``'I'``) array and passing the object makes pyvroom's
    ``isinstance(..., _vroom.Matrix)`` guard skip that cast. Values must be
    non-negative and fit in uint32 (our scaled distances do). See
    PYVROOM_COMPATIBILITY_ISSUE.md.
    """
    from vroom import _vroom

    return _vroom.Matrix(np.ascontiguousarray(matrix_int, dtype=np.uintc))


def _build_input(instance: Instance, scale: int):
    """Translate an :class:`Instance` into a ``vroom.Input`` (CVRP, VRPTW or MDVRP).

    Returns ``(problem, vehicle_depot)``; ``vehicle_depot`` is ``None`` for the
    single-depot variants and, for MDVRP, maps each vehicle id to its fixed depot
    node (used to recover per-route depots from the solution).

    The authoritative distance matrix, scaled and rounded to ints, is fed as
    VROOM's duration matrix (cost objective and, for VRPTW, the travel-time
    basis). Jobs use ``id == location ==`` customer index so solution rows map
    straight back to our indices. For VRPTW each job also carries its scaled
    service duration (``default_service``) and time window, and every vehicle
    carries the depot's time window; all of these share the same ``scale`` as the
    matrix, so VROOM sees one self-consistent time system.
    """
    import vroom

    n = instance.num_nodes
    depot = instance.depot
    demands = instance.demands

    dist_int = np.rint(instance.distance * scale).astype(np.int64)

    problem = vroom.Input()
    problem.set_durations_matrix(_PROFILE, _vroom_matrix(dist_int))

    if instance.variant == MDVRP:
        return _build_mdvrp_input(vroom, problem, instance)

    if instance.variant == VRPMPD:
        return _build_vrpmpd_input(vroom, problem, instance, dist_int)

    is_vrptw = instance.variant == VRPTW
    if is_vrptw:
        tw = instance.time_windows
        service = instance.service_times
        assert tw is not None and service is not None  # guaranteed for VRPTW
        tw_int = np.rint(tw * scale).astype(np.int64)
        svc_int = np.rint(service * scale).astype(np.int64)
        depot_tw = [int(tw_int[depot, 0]), int(tw_int[depot, 1])]
    else:
        depot_tw = None

    for i in range(n):
        if i == depot:
            continue
        if is_vrptw:
            job = vroom.Job(
                id=i,
                location=i,
                delivery=[int(demands[i])],
                default_service=int(svc_int[i]),
                time_windows=[[int(tw_int[i, 0]), int(tw_int[i, 1])]],
            )
        else:
            job = vroom.Job(id=i, location=i, delivery=[int(demands[i])])
        problem.add_job(job)

    # Generous fleet: one vehicle per customer is a safe feasibility upper bound;
    # the distance objective drives VROOM to use as few as it needs (extras stay
    # empty and are dropped during extraction).
    num_vehicles = max(1, n - 1)
    for v in range(num_vehicles):
        kwargs = dict(
            id=v,
            start=depot,
            end=depot,
            profile=_PROFILE,
            capacity=[int(instance.capacity)],
        )
        if is_vrptw:
            kwargs["time_window"] = depot_tw
        problem.add_vehicle(vroom.Vehicle(**kwargs))

    return problem, None


def _build_mdvrp_input(vroom, problem, instance: Instance):
    """Add MDVRP jobs and per-depot vehicles to ``problem``; return the map too.

    Customers become jobs (``id == location ==`` customer index); each depot gets a
    block of vehicles fixed to start and end at that depot (native multi-depot via
    per-vehicle ``start``/``end``). The generous-but-bounded per-depot fleet (see
    ``mdvrp_vehicles_per_depot``) keeps a feasible assignment available for any way
    VROOM spreads customers across depots. ``vehicle_depot`` records each vehicle's
    depot so per-route depots can be recovered from the solution.
    """
    demands = instance.demands

    for i in instance.customers:
        problem.add_job(vroom.Job(id=i, location=i, delivery=[int(demands[i])]))

    vehicles_per_depot = mdvrp_vehicles_per_depot(instance)
    vehicle_depot: dict[int, int] = {}
    vid = 0
    for d in instance.depot_indices:
        for _ in range(vehicles_per_depot):
            problem.add_vehicle(
                vroom.Vehicle(
                    id=vid,
                    start=int(d),
                    end=int(d),
                    profile=_PROFILE,
                    capacity=[int(instance.capacity)],
                )
            )
            vehicle_depot[vid] = int(d)
            vid += 1

    return problem, vehicle_depot


def _build_vrpmpd_input(vroom, problem, instance: Instance, dist_int):
    """Add VRPMPD jobs and vehicles to ``problem``; return (problem, None).

    Each customer becomes a job with both ``delivery`` (depot->customer) and
    ``pickup`` (customer->depot) amounts. VROOM tracks load step-by-step
    (position-dependent) natively when both delivery and pickup are set on a Job.
    A large per-vehicle fixed cost implements the lexicographic two-stage objective
    (minimize vehicles first, then distance). The problem returns ``None`` for
    ``vehicle_depot`` because all vehicles share the single depot.
    """
    deliveries = instance.deliveries
    pickups = instance.pickups
    assert deliveries is not None and pickups is not None

    for i in instance.customers:
        problem.add_job(
            vroom.Job(
                id=i,
                location=i,
                delivery=[int(deliveries[i])],
                pickup=[int(pickups[i])],
            )
        )

    num_v = vrpmpd_max_vehicles(instance)
    fixed = lexicographic_fixed_cost(dist_int, instance.num_nodes)
    depot = instance.depot
    for vid in range(num_v):
        problem.add_vehicle(
            vroom.Vehicle(
                id=vid,
                start=int(depot),
                end=int(depot),
                profile=_PROFILE,
                capacity=[int(instance.capacity)],
                costs=vroom.VehicleCosts(fixed=fixed),
            )
        )

    return problem, None
