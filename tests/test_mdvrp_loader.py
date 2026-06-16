"""Tests for the Cordeau MDVRP loader."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from vrpbench.core.instance import MDVRP
from vrpbench.datasets import loader

DATA = Path(__file__).parent / "data"
OLD = Path("data/instances/MDVRP/old/p01.txt")
NEW = Path("data/instances/MDVRP/new/pr01.txt")


def test_load_toy_mdvrp():
    inst = loader.load(DATA / "toy_mdvrp.txt", variant=MDVRP)
    assert inst.variant == MDVRP
    assert inst.num_nodes == 6
    assert inst.depot_indices == (0, 1)
    assert inst.depot == 0
    assert inst.capacity == 100
    # Depots come first (indices 0,1) with zero demand; 4 customers follow.
    assert list(inst.customers) == [2, 3, 4, 5]
    assert inst.demands[:2].tolist() == [0, 0]
    assert inst.demands[2:].tolist() == [10, 10, 10, 10]
    # Depot coordinates were moved to the front (file ids 5,6 -> indices 0,1).
    assert inst.coords[0].tolist() == [0.0, 0.0]
    assert inst.coords[1].tolist() == [10.0, 10.0]
    assert np.allclose(inst.distance, inst.distance.T)


def test_load_old_cordeau_p01():
    inst = loader.load(OLD, variant=MDVRP)
    assert inst.variant == MDVRP
    # header "2 4 50 4" -> 50 customers, 4 depots.
    assert inst.depot_indices == (0, 1, 2, 3)
    assert len(inst.customers) == 50
    assert inst.num_nodes == 54
    assert inst.capacity == 80  # depot line "0 80" -> Q=80
    assert inst.distance.shape == (54, 54)
    assert np.allclose(inst.distance, inst.distance.T)


def test_load_new_cordeau_pr01_floats():
    # The "new" instances carry float coordinates; the parser must not choke.
    inst = loader.load(NEW, variant=MDVRP)
    assert inst.variant == MDVRP
    assert inst.depot_indices == (0, 1, 2, 3)
    assert len(inst.customers) == 48
    # At least one coordinate is non-integer (confirms float parsing).
    assert not np.allclose(inst.coords, np.rint(inst.coords))
