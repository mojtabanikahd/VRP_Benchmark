"""Shared fixtures: small hand-built CVRP and VRPTW instances."""

from __future__ import annotations

import numpy as np
import pytest

from vrpbench.core.instance import CVRP, MDVRP, VRPTW, Instance


def _euclid(coords: np.ndarray) -> np.ndarray:
    diff = coords[:, None, :] - coords[None, :, :]
    return np.sqrt((diff**2).sum(axis=-1))


@pytest.fixture
def cvrp_instance() -> Instance:
    # depot at origin, 3 customers on a line.
    coords = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [3.0, 0.0]])
    demands = np.array([0, 1, 1, 1])
    dist = _euclid(coords)
    return Instance(
        name="toy-cvrp",
        variant=CVRP,
        num_nodes=4,
        coords=coords,
        demands=demands,
        capacity=2,
        distance=dist,
        num_vehicles=2,
    )


@pytest.fixture
def mdvrp_instance() -> Instance:
    # Two depots (indices 0,1); four customers (indices 2..5), two clustered near
    # each depot. depot 0 at origin, depot 1 at (10, 10).
    coords = np.array(
        [[0.0, 0.0], [10.0, 10.0], [1.0, 0.0], [0.0, 1.0], [10.0, 9.0], [9.0, 10.0]]
    )
    demands = np.array([0, 0, 10, 10, 10, 10])
    dist = _euclid(coords)
    return Instance(
        name="toy-mdvrp",
        variant=MDVRP,
        num_nodes=6,
        coords=coords,
        demands=demands,
        capacity=100,
        distance=dist,
        depot=0,
        depot_indices=(0, 1),
    )


@pytest.fixture
def vrptw_instance() -> Instance:
    coords = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [3.0, 0.0]])
    demands = np.array([0, 1, 1, 1])
    dist = _euclid(coords)
    # Customer 3 (distance 3 from depot) is reachable directly (arrival 3.0)
    # but not at the end of a chained route (arrival 5.0).
    time_windows = np.array(
        [[0.0, 100.0], [0.0, 50.0], [0.0, 50.0], [0.0, 4.0]]
    )
    service_times = np.array([0.0, 1.0, 1.0, 1.0])
    return Instance(
        name="toy-vrptw",
        variant=VRPTW,
        num_nodes=4,
        coords=coords,
        demands=demands,
        capacity=3,
        distance=dist,
        num_vehicles=3,
        time_windows=time_windows,
        service_times=service_times,
    )
