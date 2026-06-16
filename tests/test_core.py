"""Tests for the core data model and evaluation (Steps 1-2)."""

from __future__ import annotations

import numpy as np
import pytest

from vrpbench.core import evaluate
from vrpbench.core.instance import CVRP, Instance
from vrpbench.core.solution import Solution


def test_instance_validates_shapes(cvrp_instance: Instance):
    assert cvrp_instance.num_nodes == 4
    assert cvrp_instance.distance.shape == (4, 4)
    assert list(cvrp_instance.customers) == [1, 2, 3]


def test_instance_rejects_bad_shape():
    with pytest.raises(ValueError):
        Instance(
            name="bad",
            variant=CVRP,
            num_nodes=3,
            coords=np.zeros((2, 2)),  # wrong
            demands=np.zeros(3, dtype=int),
            capacity=1,
            distance=np.zeros((3, 3)),
        )


def test_solution_counts_vehicles():
    sol = Solution(routes=[[1, 2], [3], []], objective=0.0, feasible=True, runtime_s=0.0)
    assert sol.num_vehicles == 2


def test_verify_feasible_cvrp(cvrp_instance: Instance):
    # Two routes respecting capacity 2: [1,2] load 2, [3] load 1.
    sol = Solution(routes=[[1, 2], [3]], objective=0.0, feasible=True, runtime_s=0.1)
    ev = evaluate.verify(cvrp_instance, sol)
    assert ev.feasible
    assert ev.num_vehicles == 2
    # route [1,2]: 0->1 (1) + 1->2 (1) + 2->0 (2) = 4 ; route [3]: 3+3 = 6
    assert ev.objective == pytest.approx(10.0)


def test_verify_detects_capacity_violation(cvrp_instance: Instance):
    sol = Solution(routes=[[1, 2, 3]], objective=0.0, feasible=True, runtime_s=0.0)
    ev = evaluate.verify(cvrp_instance, sol)
    assert not ev.feasible
    assert any("capacity" in v for v in ev.violations)


def test_verify_detects_missing_customer(cvrp_instance: Instance):
    sol = Solution(routes=[[1, 2]], objective=0.0, feasible=True, runtime_s=0.0)
    ev = evaluate.verify(cvrp_instance, sol)
    assert not ev.feasible
    assert any("unvisited" in v for v in ev.violations)


def test_verify_obj_mismatch(cvrp_instance: Instance):
    sol = Solution(routes=[[1, 2], [3]], objective=999.0, feasible=True, runtime_s=0.0)
    ev = evaluate.verify(cvrp_instance, sol)
    assert ev.obj_mismatch == pytest.approx(989.0)


def test_verify_feasible_vrptw(vrptw_instance: Instance):
    # Visit 3 first (closes at 2.5): arrival 3.0 -> infeasible if alone after others.
    # Feasible plan: each customer on its own short route.
    sol = Solution(routes=[[1], [2], [3]], objective=0.0, feasible=True, runtime_s=0.0)
    ev = evaluate.verify(vrptw_instance, sol)
    assert ev.feasible, ev.violations


def test_verify_detects_time_window_violation(vrptw_instance: Instance):
    # Route [1,2,3]: arrival at 3 = 1(->1)+1(svc)+1(->2)+1(svc)+1(->3)=5 > 2.5.
    sol = Solution(routes=[[1, 2, 3]], objective=0.0, feasible=True, runtime_s=0.0)
    ev = evaluate.verify(vrptw_instance, sol)
    assert not ev.feasible
    assert any("latest" in v for v in ev.violations)


def test_mdvrp_customers_skip_all_depots(mdvrp_instance: Instance):
    # Two depots at indices 0,1 -> customers start at index 2.
    assert list(mdvrp_instance.customers) == [2, 3, 4, 5]


def test_mdvrp_route_distance_anchors_to_given_depot(mdvrp_instance: Instance):
    # Route [2,3] from depot 0 is short; from depot 1 it is far. The depot
    # argument must change the first/last legs accordingly.
    near = evaluate.route_distance(mdvrp_instance, [2, 3], depot=0)
    far = evaluate.route_distance(mdvrp_instance, [2, 3], depot=1)
    assert near < far
    # Default depot is instance.depot (0) -> matches the depot=0 anchoring.
    assert evaluate.route_distance(mdvrp_instance, [2, 3]) == pytest.approx(near)


def test_mdvrp_verify_uses_per_route_depots(mdvrp_instance: Instance):
    # Cluster {2,3} served by depot 0, cluster {4,5} by depot 1.
    sol = Solution(
        routes=[[2, 3], [4, 5]],
        objective=0.0,
        feasible=True,
        runtime_s=0.0,
        route_depots=[0, 1],
    )
    ev = evaluate.verify(mdvrp_instance, sol)
    assert ev.feasible, ev.violations
    assert ev.num_vehicles == 2


def test_mdvrp_verify_flags_invalid_depot(mdvrp_instance: Instance):
    sol = Solution(
        routes=[[2, 3], [4, 5]],
        objective=0.0,
        feasible=True,
        runtime_s=0.0,
        route_depots=[0, 9],  # 9 is not a depot
    )
    ev = evaluate.verify(mdvrp_instance, sol)
    assert not ev.feasible
    assert any("invalid depots" in v for v in ev.violations)


def test_mdvrp_verify_flags_route_depots_length_mismatch(mdvrp_instance: Instance):
    sol = Solution(
        routes=[[2, 3], [4, 5]],
        objective=0.0,
        feasible=True,
        runtime_s=0.0,
        route_depots=[0],  # too short
    )
    ev = evaluate.verify(mdvrp_instance, sol)
    assert not ev.feasible
    assert any("route_depots length" in v for v in ev.violations)


def test_gap():
    assert evaluate.gap(110.0, 100.0) == pytest.approx(10.0)
    assert evaluate.gap(100.0, 100.0) == pytest.approx(0.0)
    assert evaluate.gap(100.0, None) is None
