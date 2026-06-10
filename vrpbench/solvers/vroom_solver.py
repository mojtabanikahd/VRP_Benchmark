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

from vrpbench.core.instance import CVRP, VRPTW, Instance
from vrpbench.core.solution import Solution
from vrpbench.solvers.base import SolverError

_SCALE = {CVRP: 1, VRPTW: 10}
_PROFILE = "car"


class VroomSolver:
    name = "vroom"
    supported_variants = (CVRP, VRPTW)

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
        problem = _build_input(instance, scale)

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

        return _to_solution(result, scale, runtime_s)

    def version(self) -> str:
        """Return the pyvroom package version (recorded for reproducibility)."""
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("pyvroom")
        except PackageNotFoundError:  # pragma: no cover
            return "unknown"


def _to_solution(result, scale: int, runtime_s: float) -> Solution:
    """Convert a VROOM solution into our canonical :class:`Solution`.

    ``result.routes`` is a per-step ``pandas.DataFrame``; we group by
    ``vehicle_id``, keep ``type == "job"`` rows in order, and collect their ``id``
    (== our customer index) into one list per non-empty route. ``summary.cost`` is
    the scaled distance; descaling yields VROOM's own objective claim. Any
    unassigned job marks the solution infeasible (the evaluator re-verifies).
    """
    df = result.routes
    routes: list[list[int]] = []
    for vehicle_id in df["vehicle_id"].unique():
        steps = df[df["vehicle_id"] == vehicle_id]
        route = [int(i) for i in steps.loc[steps["type"] == "job", "id"]]
        if route:
            routes.append(route)

    return Solution(
        routes=routes,
        objective=float(result.summary.cost) / scale,
        feasible=int(result.summary.unassigned) == 0,
        runtime_s=runtime_s,
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
    """Translate an :class:`Instance` into a ``vroom.Input`` (CVRP or VRPTW).

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

    return problem
