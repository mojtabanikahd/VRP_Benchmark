"""Tests for the VROOM adapter (Step 8)."""

from __future__ import annotations

from pathlib import Path

import pytest

from vrpbench.core import evaluate
from vrpbench.datasets import loader
from vrpbench.solvers.vroom_solver import VroomSolver

DATA = Path(__file__).parent / "data"


def test_vroom_solves_cvrp():
    inst = loader.load(DATA / "toy.vrp")
    sol = VroomSolver().solve(inst, time_budget_s=1.0, seed=0)
    ev = evaluate.verify(inst, sol)
    assert ev.feasible, ev.violations
    assert sol.runtime_s > 0
    # toy optimum is 8 (verified independently)
    assert ev.objective == pytest.approx(8.0)
    # solver's reported objective matches our recompute (integer CVRP, scale 1)
    assert ev.obj_mismatch == pytest.approx(0.0, abs=1e-6)


def test_vroom_solves_vrptw():
    inst = loader.load(DATA / "toy_solomon.txt")
    sol = VroomSolver().solve(inst, time_budget_s=1.0, seed=0)
    ev = evaluate.verify(inst, sol)
    assert ev.feasible, ev.violations
    assert ev.objective > 0


def test_vroom_deterministic_per_seed():
    inst = loader.load(DATA / "toy.vrp")
    a = VroomSolver().solve(inst, time_budget_s=1.0, seed=42)
    b = VroomSolver().solve(inst, time_budget_s=1.0, seed=42)
    assert a.routes == b.routes


def test_vroom_version():
    assert VroomSolver().version() != "unknown"
