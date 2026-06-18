"""Tests for the PVRP (Cordeau ``.txt``) file loader."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from vrpbench.core.instance import PVRP, VRPTW
from vrpbench.datasets import loader

P01 = Path("data/instances/PVRP/old/p01.txt")
PR01 = Path("data/instances/PVRP/new/pr01.txt")


@pytest.mark.skipif(not P01.exists(), reason="PVRP instances not present")
def test_load_p01_basic_shape():
    inst = loader.load(P01, variant="PVRP")
    assert inst.variant == PVRP
    # header: type=1 m=3 n=51 t=2  ->  n+1 = 52 nodes, depot id 0.
    assert inst.num_nodes == 52
    assert inst.capacity == 160
    assert inst.periods == 2
    assert inst.max_vehicles_per_day == 3
    assert inst.depot == 0
    assert inst.depot_indices is None
    # old set: no route-duration limit and no service times.
    assert inst.max_route_duration == 0.0
    assert float(inst.service_times.sum()) == 0.0


@pytest.mark.skipif(not P01.exists(), reason="PVRP instances not present")
def test_load_p01_freq_and_combinations():
    inst = loader.load(P01, variant="PVRP")
    assert inst.freq is not None and inst.combinations is not None
    # Depot carries no visits / combinations.
    assert int(inst.freq[0]) == 0
    assert inst.combinations[0] == []
    # Every customer's combination codes have popcount == freq (the bitmask
    # encodes exactly `freq` visit days).
    for c in range(1, inst.num_nodes):
        assert len(inst.combinations[c]) >= 1
        for code in inst.combinations[c]:
            assert bin(code).count("1") == int(inst.freq[c])
    # p01 customers are visited once on either day (combos [1, 2]).
    assert inst.combinations[1] == [1, 2]
    assert int(inst.freq[1]) == 1


@pytest.mark.skipif(not P01.exists(), reason="PVRP instances not present")
def test_load_p01_integer_distance_matrix():
    inst = loader.load(P01, variant="PVRP")
    assert inst.distance.shape == (52, 52)
    np.testing.assert_array_equal(inst.distance, np.rint(inst.distance))
    np.testing.assert_array_almost_equal(inst.distance, inst.distance.T)
    np.testing.assert_array_equal(np.diag(inst.distance), np.zeros(52))


@pytest.mark.skipif(not PR01.exists(), reason="PVRP instances not present")
def test_load_pr01_new_set_duration_and_service():
    inst = loader.load(PR01, variant="PVRP")
    assert inst.variant == PVRP
    # header: type=1 m=2 n=48 t=4  ->  49 nodes.
    assert inst.num_nodes == 49
    assert inst.periods == 4
    assert inst.max_vehicles_per_day == 2
    assert inst.capacity == 200
    # new set: a positive route-duration limit and non-zero service times.
    assert inst.max_route_duration == 500.0
    assert inst.service_times is not None
    assert float(inst.service_times.sum()) > 0.0
    assert inst.service_times[0] == 0.0  # depot has no service time


@pytest.mark.skipif(not P01.exists(), reason="PVRP instances not present")
def test_pvrp_requires_explicit_variant():
    # `.txt` is shared with Solomon VRPTW, so without variant=PVRP the loader
    # must not silently treat the file as VRPTW.
    with pytest.raises(Exception):
        loader.load(P01)  # inferred as Solomon VRPTW -> parse/validation failure
