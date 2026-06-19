"""Tests for the SDVRP (Cordeau ``.txt``, type=3) file loader.

Combination codes are MSB-first bitmasks over the t vehicle types: in a t-bit string
the leftmost bit is the first type line. So for t=3, code 4 (=100) selects type index
0, code 2 (=010) selects type 1, and code 1 (=001) selects type 2.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from vrpbench.core.instance import SDVRP
from vrpbench.datasets import loader
from vrpbench.datasets.loader import _types_of

P01 = Path("data/instances/SDVRP/old/p01.txt")
PR01 = Path("data/instances/SDVRP/new/pr01.txt")


def test_types_of_is_msb_first():
    # README example uses left-to-right numbering; verify the t=3 / t=4 decodings.
    assert _types_of(4, 3) == [0]      # 100
    assert _types_of(2, 3) == [1]      # 010
    assert _types_of(1, 3) == [2]      # 001
    assert _types_of(7, 3) == [0, 1, 2]  # 111
    assert _types_of(8, 4) == [0]      # 1000
    assert _types_of(1, 4) == [3]      # 0001


@pytest.mark.skipif(not P01.exists(), reason="SDVRP instances not present")
def test_load_p01_basic_shape():
    inst = loader.load(P01, variant="SDVRP")
    assert inst.variant == SDVRP
    # header: type=3 m=5 n=55 t=3  ->  n+1 = 56 nodes, depot id 0.
    assert inst.num_nodes == 56
    assert inst.num_vehicle_types == 3
    assert inst.vehicles_per_type == 5
    assert inst.depot == 0
    assert inst.depot_indices is None
    # old set type lines: D Q = (0, 60), (0, 120), (0, 160).
    assert inst.vehicle_capacities == (60, 120, 160)
    assert inst.vehicle_durations == (0.0, 0.0, 0.0)
    assert inst.capacity == 160  # max type capacity (interface compatibility)
    # old set: no service times.
    assert float(inst.service_times.sum()) == 0.0


@pytest.mark.skipif(not P01.exists(), reason="SDVRP instances not present")
def test_load_p01_allowed_types_msb_first():
    inst = loader.load(P01, variant="SDVRP")
    assert inst.allowed_types is not None
    assert inst.allowed_types[0] == frozenset()  # depot never routed
    # customer 1: codes [4, 2] -> types {0, 1}.
    assert inst.allowed_types[1] == frozenset({0, 1})
    # customer 51 (demand 60, code 4) -> only type 0 (capacity 60), fits exactly.
    assert inst.allowed_types[51] == frozenset({0})
    assert int(inst.demands[51]) == 60
    # customer 53 (demand 160, code 1) -> only type 2 (capacity 160), fits exactly.
    assert inst.allowed_types[53] == frozenset({2})
    assert int(inst.demands[53]) == 160
    # every customer's demand fits in at least one allowed type (no forced split).
    for c in range(1, inst.num_nodes):
        assert max(inst.vehicle_capacities[t] for t in inst.allowed_types[c]) >= int(
            inst.demands[c]
        )


@pytest.mark.skipif(not P01.exists(), reason="SDVRP instances not present")
def test_load_p01_integer_distance_matrix():
    inst = loader.load(P01, variant="SDVRP")
    assert inst.distance.shape == (56, 56)
    np.testing.assert_array_equal(inst.distance, np.rint(inst.distance))
    np.testing.assert_array_almost_equal(inst.distance, inst.distance.T)
    np.testing.assert_array_equal(np.diag(inst.distance), np.zeros(56))


@pytest.mark.skipif(not PR01.exists(), reason="SDVRP instances not present")
def test_load_pr01_new_set_durations_and_service():
    inst = loader.load(PR01, variant="SDVRP")
    assert inst.variant == SDVRP
    # header: type=3 m=1 n=48 t=4  ->  49 nodes.
    assert inst.num_nodes == 49
    assert inst.num_vehicle_types == 4
    assert inst.vehicles_per_type == 1
    # new set type lines: D Q = (500, 100), (500, 150), (500, 200), (500, 250).
    assert inst.vehicle_capacities == (100, 150, 200, 250)
    assert inst.vehicle_durations == (500.0, 500.0, 500.0, 500.0)
    assert inst.capacity == 250
    # new set: non-zero service times; depot has none.
    assert inst.service_times is not None
    assert float(inst.service_times.sum()) > 0.0
    assert inst.service_times[0] == 0.0
    # customer 1: codes [1,2,4,8] -> all four types.
    assert inst.allowed_types[1] == frozenset({0, 1, 2, 3})


@pytest.mark.skipif(not P01.exists(), reason="SDVRP instances not present")
def test_sdvrp_requires_explicit_variant():
    # `.txt` is shared with Solomon VRPTW, so without variant=SDVRP the loader must
    # not silently treat the file as VRPTW.
    with pytest.raises(Exception):
        loader.load(P01)
