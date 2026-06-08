"""Tests for the dataset loader and BKS table (Step 3)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from vrpbench.core.instance import CVRP, VRPTW
from vrpbench.datasets import bks, loader

DATA = Path(__file__).parent / "data"


def test_load_cvrp():
    inst = loader.load(DATA / "toy.vrp")
    assert inst.variant == CVRP
    assert inst.num_nodes == 4
    assert inst.capacity == 2
    assert inst.demands[inst.depot] == 0
    assert inst.distance.shape == (4, 4)
    # symmetric, zero diagonal
    assert np.allclose(inst.distance, inst.distance.T)
    assert np.allclose(np.diag(inst.distance), 0.0)
    # integer rounding convention for CVRP EUC_2D
    assert np.allclose(inst.distance, np.round(inst.distance))


def test_load_vrptw():
    inst = loader.load(DATA / "toy_solomon.txt")
    assert inst.variant == VRPTW
    assert inst.num_nodes == 4
    assert inst.time_windows is not None and inst.time_windows.shape == (4, 2)
    assert inst.service_times is not None and inst.service_times.shape == (4,)
    assert inst.num_vehicles == 3
    # float Euclidean convention (not all integers here)
    assert not np.allclose(inst.distance, np.round(inst.distance))


def test_variant_mismatch_raises():
    with pytest.raises(ValueError):
        loader.load(DATA / "toy.vrp", variant=VRPTW)


def test_unknown_extension_raises(tmp_path):
    p = tmp_path / "instance.dat"
    p.write_text("noop")
    with pytest.raises(ValueError):
        loader.load(p)


def test_bks_lookup():
    table = bks.load_bks("data/bks.csv")
    assert len(table) > 0
    assert table.lookup("X-n101-k25") == pytest.approx(27591)
    # case-insensitive
    assert table.lookup("x-n101-k25") == pytest.approx(27591)
    assert table.lookup("does-not-exist") is None


def test_bks_missing_file_is_empty(tmp_path):
    table = bks.load_bks(tmp_path / "nope.csv")
    assert len(table) == 0
    assert table.lookup("anything") is None
