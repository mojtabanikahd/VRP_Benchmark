"""Tests for the VRPSolverEasy adapter (exact BCP solver via BaPCod)."""

from __future__ import annotations

from pathlib import Path

import pytest

from vrpbench.core import evaluate
from vrpbench.datasets import loader
from vrpbench.solvers.base import SolverError

pytest.importorskip("VRPSolverEasy")

from vrpbench.solvers.vrpsolvereasy_solver import VRPSolverEasySolver

DATA = Path(__file__).parent / "data"


def pytest_configure(config):
    """Module-level setup: verify BaPCod shared library is available.

    Skip the entire test module if the library cannot be loaded, keeping the
    suite green on machines without BaPCod while fully testing configured ones.
    """
    try:
        # Quick 3-point solve attempt to confirm the engine is ready
        from VRPSolverEasy.src import solver

        m = solver.Model()
        m.add_vehicle_type(id=1, start_point_id=0, end_point_id=0, max_number=1,
                           capacity=100, var_cost_dist=1, tw_begin=0, tw_end=100)
        m.add_depot(id=0, service_time=0, tw_begin=0, tw_end=100)
        m.add_customer(id=1, demand=10, service_time=0, tw_begin=0, tw_end=100)
        m.add_link(start_point_id=0, end_point_id=1, distance=10, time=10)
        m.set_parameters(time_limit=1.0, solver_name="CLP")
        m.solve()
        # If we reach here, the library is loaded and functional
    except Exception as e:
        pytest.skip(
            f"BaPCod library not available or solver setup failed: {e}. "
            f"See BAPCOD_SETUP.md for installation instructions."
        )


def test_vrpsolvereasy_solves_cvrp():
    """Exact solver should find the proven optimum (8.0) for toy CVRP."""
    inst = loader.load(DATA / "toy.vrp")
    sol = VRPSolverEasySolver().solve(inst, time_budget_s=10.0, seed=0)
    ev = evaluate.verify(inst, sol)
    assert ev.feasible, ev.violations
    assert sol.runtime_s > 0
    # toy optimum is 8 (verified independently); exact solver finds it
    assert ev.objective == pytest.approx(8.0)
    # solver's reported objective matches our recompute (integer CVRP, scale 1)
    assert ev.obj_mismatch == pytest.approx(0.0, abs=1e-6)


def test_vrpsolvereasy_solves_vrptw():
    """Exact solver handles VRPTW with service times and time windows."""
    inst = loader.load(DATA / "toy_solomon.txt")
    sol = VRPSolverEasySolver().solve(inst, time_budget_s=10.0, seed=0)
    ev = evaluate.verify(inst, sol)
    assert ev.feasible, ev.violations
    assert ev.objective > 0


def test_vrpsolvereasy_deterministic_per_seed():
    """BCP with fixed time budget is deterministic (seed has no effect)."""
    inst = loader.load(DATA / "toy.vrp")
    a = VRPSolverEasySolver().solve(inst, time_budget_s=10.0, seed=42)
    b = VRPSolverEasySolver().solve(inst, time_budget_s=10.0, seed=42)
    # toy reaches proven optimality well within 10s; routes should be identical
    assert a.routes == b.routes


def test_vrpsolvereasy_version():
    """Version string is not unknown (engine is configured)."""
    assert VRPSolverEasySolver().version() != "unknown"


def test_vrpsolvereasy_rejects_oversized_instance():
    """Adapter rejects instances larger than VRPSolver's 1022-node hard limit."""
    from vrpbench.core.instance import Instance, CVRP
    import numpy as np

    n = 1500
    inst = Instance(
        name="too_large",
        variant=CVRP,
        num_nodes=n,
        coords=np.zeros((n, 2)),
        demands=np.zeros(n, dtype=int),
        capacity=100,
        distance=np.zeros((n, n)),
    )

    with pytest.raises(SolverError, match="hard limit"):
        VRPSolverEasySolver().solve(inst, time_budget_s=1.0, seed=0)
