"""Pluggable solver adapters.

Solvers are registered by name in :data:`SOLVERS`. Adding a new solver (e.g. a
future custom method) means writing one adapter that satisfies the
:class:`~vrpbench.solvers.base.Solver` protocol and adding one entry here.
"""

from __future__ import annotations

from vrpbench.solvers.base import Solver, SolverError

# Lazy registry: name -> zero-arg factory. Imports are deferred so that a missing
# optional dependency (e.g. ortools) does not break unrelated solvers.


def _make_pyvrp() -> Solver:
    from vrpbench.solvers.pyvrp_solver import PyVRPSolver

    return PyVRPSolver()


def _make_ortools() -> Solver:
    from vrpbench.solvers.ortools_solver import OrToolsSolver

    return OrToolsSolver()


def _make_vroom() -> Solver:
    from vrpbench.solvers.vroom_solver import VroomSolver

    return VroomSolver()


def _make_vrpsolvereasy() -> Solver:
    from vrpbench.solvers.vrpsolvereasy_solver import VRPSolverEasySolver

    return VRPSolverEasySolver()


def _make_pvrp(base_factory) -> "callable[[], Solver]":
    """Build a factory for a PVRP wrapper around a base solver factory."""

    def factory() -> Solver:
        from vrpbench.solvers.pvrp_solver import PVRPSolver

        return PVRPSolver(base_factory())

    return factory


def _make_sdvrp(base_factory=None) -> "callable[[], Solver]":
    """Build a factory for the SDVRP Tabu Search.

    ``base_factory is None`` → standalone ``sdvrp_tabu`` (greedy-NN init). Otherwise the
    wrapped base solver provides the initial solution only.
    """

    def factory() -> Solver:
        from vrpbench.solvers.sdvrp_solver import SDVRPSolver

        return SDVRPSolver(base_factory() if base_factory is not None else None)

    return factory


SOLVERS: dict[str, "callable[[], Solver]"] = {
    "pyvrp": _make_pyvrp,
    "ortools": _make_ortools,
    "vroom": _make_vroom,
    "vrpsolvereasy": _make_vrpsolvereasy,
    # Periodic VRP: ALNS over day-combination assignments, base solver routes days.
    "pvrp_pyvrp": _make_pvrp(_make_pyvrp),
    "pvrp_ortools": _make_pvrp(_make_ortools),
    "pvrp_vroom": _make_pvrp(_make_vroom),
    # Split Delivery VRP R1: homogeneous wrapper; base solver seeds the init.
    "sdvrp_tabu": _make_sdvrp(None),
    "sdvrp_pyvrp": _make_sdvrp(_make_pyvrp),
    "sdvrp_ortools": _make_sdvrp(_make_ortools),
    "sdvrp_vroom": _make_sdvrp(_make_vroom),
}


def get_solver(name: str) -> Solver:
    """Instantiate a solver by registry name."""
    if name not in SOLVERS:
        raise KeyError(f"unknown solver {name!r}; available: {sorted(SOLVERS)}")
    return SOLVERS[name]()


__all__ = ["Solver", "SolverError", "SOLVERS", "get_solver"]
