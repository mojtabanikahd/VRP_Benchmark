"""Tests for the VRPMPD (.vrpmpd) file loader."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from vrpbench.core.instance import VRPMPD
from vrpbench.datasets import loader

# Use the real CMT01H instance shipped with the repository.
CMT01H = Path("data/instances/S/CMT01H.vrpmpd")


@pytest.mark.skipif(not CMT01H.exists(), reason="S instances not present")
def test_load_cmt01h_basic_shape():
    inst = loader.load(CMT01H)
    assert inst.variant == VRPMPD
    # DIMENSION : 51 (1 depot + 50 customers)
    assert inst.num_nodes == 51
    assert inst.capacity == 160
    assert inst.depot == 0
    assert inst.depot_indices is None  # single-depot variant


@pytest.mark.skipif(not CMT01H.exists(), reason="S instances not present")
def test_load_cmt01h_customers():
    inst = loader.load(CMT01H)
    assert list(inst.customers) == list(range(1, 51))


@pytest.mark.skipif(not CMT01H.exists(), reason="S instances not present")
def test_load_cmt01h_depot_zero_loads():
    inst = loader.load(CMT01H)
    assert inst.pickups is not None
    assert inst.deliveries is not None
    # Depot (index 0) must have zero pickup and delivery.
    assert inst.pickups[0] == 0
    assert inst.deliveries[0] == 0


@pytest.mark.skipif(not CMT01H.exists(), reason="S instances not present")
def test_load_cmt01h_demands_mirror_deliveries():
    inst = loader.load(CMT01H)
    # demands is set to deliveries for interface compatibility.
    np.testing.assert_array_equal(inst.demands, inst.deliveries)


@pytest.mark.skipif(not CMT01H.exists(), reason="S instances not present")
def test_load_cmt01h_integer_distance_matrix():
    inst = loader.load(CMT01H)
    assert inst.distance.shape == (51, 51)
    # Integer-rounded Euclidean: all values should be whole numbers.
    np.testing.assert_array_equal(inst.distance, np.rint(inst.distance))
    # Symmetric.
    np.testing.assert_array_almost_equal(inst.distance, inst.distance.T)
    # Zero diagonal.
    np.testing.assert_array_equal(np.diag(inst.distance), np.zeros(51))


@pytest.mark.skipif(not CMT01H.exists(), reason="S instances not present")
def test_load_cmt01h_each_customer_pure_pickup_or_delivery():
    inst = loader.load(CMT01H)
    # In these instances each customer is either a pure delivery or pure pickup node.
    assert inst.pickups is not None
    assert inst.deliveries is not None
    for i in range(1, inst.num_nodes):
        p, d = int(inst.pickups[i]), int(inst.deliveries[i])
        assert (p == 0) != (d == 0), (
            f"customer {i} has pickup={p} and delivery={d} (expected exactly one non-zero)"
        )


@pytest.mark.skipif(not CMT01H.exists(), reason="S instances not present")
def test_load_vrpmpd_explicit_variant_arg():
    # Explicit variant= argument must match the file extension.
    inst = loader.load(CMT01H, variant=VRPMPD)
    assert inst.variant == VRPMPD


@pytest.mark.skipif(not CMT01H.exists(), reason="S instances not present")
def test_load_vrpmpd_wrong_variant_raises():
    from vrpbench.core.instance import CVRP

    with pytest.raises(ValueError, match="declared variant"):
        loader.load(CMT01H, variant=CVRP)
