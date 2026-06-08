"""Tests for the OR-Tools adapter (Steps 5 & 8)."""

from __future__ import annotations

from pathlib import Path

import pytest

from vrpbench.core import evaluate
from vrpbench.datasets import loader
from vrpbench.solvers.ortools_solver import OrToolsSolver

DATA = Path(__file__).parent / "data"


def test_ortools_solves_cvrp():
    inst = loader.load(DATA / "toy.vrp")
    sol = OrToolsSolver().solve(inst, time_budget_s=1.0, seed=0)
    ev = evaluate.verify(inst, sol)
    assert ev.feasible, ev.violations
    assert ev.objective == pytest.approx(8.0)
    # integer CVRP -> solver objective matches recompute exactly
    assert ev.obj_mismatch == pytest.approx(0.0, abs=1e-6)


def test_ortools_solves_vrptw():
    inst = loader.load(DATA / "toy_solomon.txt")
    sol = OrToolsSolver().solve(inst, time_budget_s=1.0, seed=0)
    ev = evaluate.verify(inst, sol)
    assert ev.feasible, ev.violations
    assert ev.objective > 0


def test_ortools_version():
    assert OrToolsSolver().version() != "unknown"
