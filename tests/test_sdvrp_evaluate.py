"""Tests for canonical homogeneous SDVRP split-delivery checking."""

from __future__ import annotations

import numpy as np
import pytest

from vrpbench.core import evaluate
from vrpbench.core.instance import SDVRP, Instance
from vrpbench.core.solution import Solution


def _toy() -> Instance:
    coords = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [3.0, 0.0]])
    diff = coords[:, None, :] - coords[None, :, :]
    return Instance(
        name="toy-sdvrp",
        variant=SDVRP,
        num_nodes=4,
        coords=coords,
        demands=np.array([0, 5, 8, 15], dtype=int),
        capacity=20,
        distance=np.floor(np.sqrt((diff**2).sum(axis=-1)) + 0.5),
        depot=0,
    )


def test_sdvrp_feasible_split_solution_passes():
    inst = _toy()
    sol = Solution(
        routes=[[2, 3], [1, 3]],
        objective=12.0,
        feasible=True,
        runtime_s=0.0,
        route_deliveries=[{2: 8, 3: 12}, {1: 5, 3: 3}],
    )
    ev = evaluate.verify(inst, sol)
    assert ev.feasible, ev.violations
    assert ev.objective == pytest.approx(12.0)
    assert ev.obj_mismatch == pytest.approx(0.0)


def test_sdvrp_capacity_violation_flagged():
    inst = _toy()
    sol = Solution(
        routes=[[1, 2, 3]],
        objective=0.0,
        feasible=True,
        runtime_s=0.0,
        route_deliveries=[{1: 5, 2: 8, 3: 15}],
    )
    ev = evaluate.verify(inst, sol)
    assert not ev.feasible
    assert any("capacity" in v for v in ev.violations)


def test_sdvrp_demand_coverage_violation_flagged():
    inst = _toy()
    sol = Solution(
        routes=[[2, 3], [1]],
        objective=0.0,
        feasible=True,
        runtime_s=0.0,
        route_deliveries=[{2: 8, 3: 10}, {1: 5}],
    )
    ev = evaluate.verify(inst, sol)
    assert not ev.feasible
    assert any("required demand" in v for v in ev.violations)


def test_sdvrp_has_no_hard_fleet_cap_or_vehicle_type_requirement():
    inst = _toy()
    sol = Solution(
        routes=[[1], [2], [3]],
        objective=12.0,
        feasible=True,
        runtime_s=0.0,
        route_deliveries=[{1: 5}, {2: 8}, {3: 15}],
    )
    ev = evaluate.verify(inst, sol)
    assert ev.feasible, ev.violations


def test_sdvrp_delivery_keys_must_match_route():
    inst = _toy()
    sol = Solution(
        routes=[[2, 3], [1, 3]],
        objective=0.0,
        feasible=True,
        runtime_s=0.0,
        route_deliveries=[{2: 8}, {1: 5, 3: 15}],
    )
    ev = evaluate.verify(inst, sol)
    assert not ev.feasible
    assert any("do not match route customers" in v for v in ev.violations)


def test_sdvrp_duplicate_customer_in_route_rejected():
    inst = _toy()
    sol = Solution(
        routes=[[1, 1], [2], [3]],
        objective=0.0,
        feasible=True,
        runtime_s=0.0,
        route_deliveries=[{1: 5}, {2: 8}, {3: 15}],
    )
    ev = evaluate.verify(inst, sol)
    assert not ev.feasible
    assert any("duplicate customers" in v for v in ev.violations)


def test_sdvrp_requires_delivery_maps():
    inst = _toy()
    sol = Solution(routes=[[1], [2], [3]], objective=0.0, feasible=True, runtime_s=0.0)
    ev = evaluate.verify(inst, sol)
    assert not ev.feasible
    assert any("route_deliveries length" in v for v in ev.violations)
