"""Tests for the shared AASA-to-CVRP SDVRP adapter."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from vrpbench.core import evaluate
from vrpbench.core.instance import CVRP, SDVRP, Instance
from vrpbench.core.solution import Solution
from vrpbench.datasets import loader
from vrpbench.solvers.aasa_solver import AASASolver, decode_aasa, transform_aasa
from vrpbench.solvers.base import SolverError
from vrpbench.solvers.pyvrp_solver import PyVRPSolver
from vrpbench.solvers.vroom_solver import VroomSolver


SD1 = Path("data/instances/SDVRP_R1_instances/SET-1/SD1.txt")


def _toy() -> Instance:
    coords = np.array([[0.0, 0.0], [1.0, 0.0], [10.0, 0.0]])
    diff = coords[:, None, :] - coords[None, :, :]
    return Instance(
        name="toy-sdvrp",
        variant=SDVRP,
        num_nodes=3,
        coords=coords,
        demands=np.array([0, 60, 60]),
        capacity=100,
        distance=np.floor(np.sqrt((diff**2).sum(axis=-1)) + 0.5),
    )


@pytest.mark.skipif(not SD1.exists(), reason="SD1 instance not present")
def test_aasa_sd1_produces_published_18_virtual_customers():
    original = loader.load(SD1, variant=SDVRP)
    transformed = transform_aasa(original)

    assert transformed.instance.variant == CVRP
    assert transformed.instance.num_nodes == 19
    for customer in original.customers:
        nodes = [
            node
            for node in transformed.instance.customers
            if transformed.parents[node] == customer
        ]
        assert sum(transformed.quantities[node] for node in nodes) == original.demands[customer]
        assert all(
            np.array_equal(transformed.instance.coords[node], original.coords[customer])
            for node in nodes
        )


def test_aasa_uses_parent_distances_and_coarser_fragments_farther_away():
    original = _toy()
    transformed = transform_aasa(original)

    for a in range(transformed.instance.num_nodes):
        for b in range(transformed.instance.num_nodes):
            assert transformed.instance.distance[a, b] == original.distance[
                transformed.parents[a], transformed.parents[b]
            ]

    near = [
        transformed.quantities[node]
        for node in transformed.instance.customers
        if transformed.parents[node] == 1
    ]
    far = [
        transformed.quantities[node]
        for node in transformed.instance.customers
        if transformed.parents[node] == 2
    ]
    assert max(far) >= max(near)
    assert transformed.instance.max_vehicles is not None


def test_aasa_decode_aggregates_colocated_clones_and_verifies():
    original = _toy()
    transformed = transform_aasa(original)
    by_parent = {
        customer: [
            node
            for node in transformed.instance.customers
            if transformed.parents[node] == customer
        ]
        for customer in original.customers
    }
    base = Solution(
        routes=[by_parent[1], by_parent[2]],
        objective=0.0,
        feasible=True,
        runtime_s=0.1,
    )

    decoded = decode_aasa(original, transformed, base, runtime_s=0.2)

    assert decoded.routes == [[1], [2]]
    assert decoded.route_deliveries == [{1: 60}, {2: 60}]
    assert decoded.route_vehicle_types == []
    evaluation = evaluate.verify(original, decoded)
    assert evaluation.feasible, evaluation.violations
    assert evaluation.obj_mismatch == pytest.approx(0.0)


def test_aasa_decode_rejects_missing_or_repeated_virtual_customers():
    original = _toy()
    transformed = transform_aasa(original)
    nodes = list(transformed.instance.customers)

    with pytest.raises(SolverError, match="missing virtual"):
        decode_aasa(
            original,
            transformed,
            Solution(routes=[nodes[:-1]], objective=0, feasible=True, runtime_s=0),
            runtime_s=0,
        )
    with pytest.raises(SolverError, match="repeated virtual"):
        decode_aasa(
            original,
            transformed,
            Solution(routes=[nodes + [nodes[0]]], objective=0, feasible=True, runtime_s=0),
            runtime_s=0,
        )


class _SpyCVRPSolver:
    name = "spy"
    supported_variants = (CVRP,)

    def __init__(self) -> None:
        self.calls: list[tuple[Instance, float, int]] = []

    def version(self) -> str:
        return "test"

    def solve(self, instance: Instance, *, time_budget_s: float, seed: int) -> Solution:
        self.calls.append((instance, time_budget_s, seed))
        routes: list[list[int]] = []
        current: list[int] = []
        load = 0
        for node in instance.customers:
            demand = int(instance.demands[node])
            if current and load + demand > instance.capacity:
                routes.append(current)
                current, load = [], 0
            current.append(node)
            load += demand
        if current:
            routes.append(current)
        return Solution(routes=routes, objective=0, feasible=True, runtime_s=0)


def test_aasa_wrapper_passes_cvrp_and_remaining_budget():
    base = _SpyCVRPSolver()
    solution = AASASolver(base).solve(_toy(), time_budget_s=1.0, seed=17)

    transformed, remaining, seed = base.calls[0]
    assert transformed.variant == CVRP
    assert 0 < remaining < 1.0
    assert seed == 17
    evaluation = evaluate.verify(_toy(), solution)
    assert evaluation.feasible, evaluation.violations
    assert evaluation.obj_mismatch == pytest.approx(0.0)


def test_aasa_rejects_unsupported_variant(cvrp_instance):
    with pytest.raises(SolverError, match="does not support"):
        AASASolver(_SpyCVRPSolver()).solve(cvrp_instance, time_budget_s=1, seed=0)


@pytest.mark.skipif(not SD1.exists(), reason="SD1 instance not present")
@pytest.mark.parametrize("base", [PyVRPSolver(), VroomSolver()], ids=["pyvrp", "vroom"])
def test_aasa_real_adapter_returns_feasible_split_solution(base):
    original = loader.load(SD1, variant=SDVRP)
    solution = AASASolver(base).solve(original, time_budget_s=1.0, seed=0)

    evaluation = evaluate.verify(original, solution)
    assert evaluation.feasible, evaluation.violations
    assert evaluation.obj_mismatch == pytest.approx(0.0)
    assert solution.route_vehicle_types == []
    appearances = {
        customer: sum(customer in delivered for delivered in solution.route_deliveries)
        for customer in original.customers
    }
    assert max(appearances.values()) >= 2
