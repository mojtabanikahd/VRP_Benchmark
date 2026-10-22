"""Scenario builder for the route studio."""

from __future__ import annotations

import math

import numpy as np
import pytest

from web.api.scenario import (
    STUDIO_VARIANTS,
    Scenario,
    ScenarioError,
    ScenarioNode,
    build_instance,
    preview_from_scenario,
)


def _customer(x: float, y: float, demand: int = 1, **extra) -> ScenarioNode:
    return ScenarioNode(role="customer", x=x, y=y, demand=demand, **extra)


def _depot(x: float, y: float, **extra) -> ScenarioNode:
    return ScenarioNode(role="depot", x=x, y=y, demand=0, **extra)


def test_studio_variants_exclude_pvrp():
    assert "PVRP" not in STUDIO_VARIANTS
    assert STUDIO_VARIANTS == ("CVRP", "VRPTW", "MDVRP")


def test_cvrp_distance_is_nearest_integer():
    scenario = Scenario(
        name="line",
        variant="CVRP",
        capacity=10,
        nodes=[_depot(0, 0), _customer(1, 1), _customer(2, 3)],
    )
    instance = build_instance(scenario)
    assert instance.variant == "CVRP"
    assert instance.depot_indices is None
    assert instance.distance[0, 2] == pytest.approx(round(math.sqrt(4 + 9)))
    assert instance.distance[0, 2] == 4
    assert np.array_equal(instance.distance, np.rint(instance.distance))


def test_vrptw_distance_stays_float_and_requires_windows():
    scenario = Scenario(
        name="window",
        variant="VRPTW",
        capacity=10,
        nodes=[
            _depot(0, 0, ready=0, due=100, service=0),
            _customer(1, 1, ready=0, due=50, service=5),
        ],
    )
    instance = build_instance(scenario)
    assert instance.distance[0, 1] == pytest.approx(math.sqrt(2))
    assert instance.distance[0, 1] != pytest.approx(round(math.sqrt(2)))
    assert instance.time_windows is not None
    assert instance.service_times is not None
    assert list(instance.time_windows[1]) == [0, 50]
    assert instance.service_times[1] == 5


def test_vrptw_missing_window_is_rejected():
    scenario = Scenario(
        name="window",
        variant="VRPTW",
        capacity=10,
        nodes=[_depot(0, 0, ready=0, due=10, service=0), _customer(1, 0)],
    )
    with pytest.raises(ScenarioError, match="ready, due, and service"):
        build_instance(scenario)


def test_mdvrp_depots_come_first_and_distance_is_integer():
    scenario = Scenario(
        name="two-depot",
        variant="MDVRP",
        capacity=10,
        nodes=[
            _customer(0, 1),
            _depot(10, 0),
            _customer(10, 1),
            _depot(0, 0),
        ],
    )
    preview = preview_from_scenario(scenario)
    roles = [node.role for node in preview.scenario.nodes]
    assert roles == ["depot", "depot", "customer", "customer"]
    instance = build_instance(scenario)
    assert instance.depot_indices == (0, 1)
    assert instance.depot == 0
    # Canonical order keeps depot insertion order: (10, 0), then (0, 0).
    assert tuple(instance.coords[1]) == (0, 0)
    assert instance.distance[1, 2] == 1
    assert instance.num_nodes == 4


def test_mdvrp_requires_two_depots():
    scenario = Scenario(
        name="one-depot",
        variant="MDVRP",
        capacity=10,
        nodes=[_depot(0, 0), _customer(1, 0)],
    )
    with pytest.raises(ScenarioError, match="at least two depots"):
        build_instance(scenario)


def test_demand_above_capacity_is_rejected():
    scenario = Scenario(
        name="heavy",
        variant="CVRP",
        capacity=5,
        nodes=[_depot(0, 0), _customer(1, 0, demand=6)],
    )
    with pytest.raises(ScenarioError, match="exceeds capacity"):
        build_instance(scenario)


def test_pvrp_variant_is_rejected():
    with pytest.raises(ValueError, match="PVRP"):
        Scenario(
            name="periodic",
            variant="PVRP",
            capacity=10,
            nodes=[_depot(0, 0), _customer(1, 0)],
        )
