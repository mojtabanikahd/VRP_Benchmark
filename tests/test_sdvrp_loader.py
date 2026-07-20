"""Tests for the DIMACS R1 SDVRP file loader."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from vrpbench.core.instance import SDVRP
from vrpbench.datasets import loader

R1_ROOT = Path("data/instances/SDVRP_R1_instances")


def _r1_files() -> list[Path]:
    return sorted(
        p for p in R1_ROOT.rglob("*") if p.suffix.lower() in {".txt", ".sd", ".cri"}
    )


@pytest.mark.skipif(not R1_ROOT.exists(), reason="SDVRP R1 instances not present")
def test_loads_all_95_r1_instances():
    files = _r1_files()
    assert len(files) == 95
    for path in files:
        inst = loader.load(path, variant="SDVRP")
        assert inst.variant == SDVRP
        assert inst.name == path.stem
        assert inst.num_nodes == len(inst.demands)
        assert inst.coords.shape == (inst.num_nodes, 2)
        assert inst.demands[0] == 0
        assert inst.capacity > 0
        assert inst.num_vehicle_types is None
        assert inst.vehicle_capacities is None
        assert inst.vehicle_durations is None
        assert inst.vehicles_per_type is None
        assert inst.allowed_types is None


@pytest.mark.skipif(not R1_ROOT.exists(), reason="SDVRP R1 instances not present")
@pytest.mark.parametrize(
    "path",
    [
        R1_ROOT / "SET-1" / "SD1.txt",
        R1_ROOT / "SET-2" / "S51D1.sd",
        R1_ROOT / "SET-3" / "p01_00.cri",
    ],
)
def test_detects_r1_extensions_and_txt_content(path):
    assert loader.detect_format(path) == ("sdvrp", SDVRP)
    inst = loader.load(path)
    assert inst.variant == SDVRP
    assert inst.name == path.stem


@pytest.mark.skipif(not R1_ROOT.exists(), reason="SDVRP R1 instances not present")
def test_load_sd1_basic_shape_and_rounding():
    inst = loader.load(R1_ROOT / "SET-1" / "SD1.txt", variant="SDVRP")
    assert inst.num_nodes == 9
    assert inst.capacity == 100
    np.testing.assert_array_equal(inst.demands, np.array([0, 60, 90, 60, 90, 60, 90, 60, 90]))
    assert inst.distance[0, 1] == 1000
    assert inst.distance[1, 2] == 1414
    np.testing.assert_array_equal(inst.distance, inst.distance.T)
    np.testing.assert_array_equal(np.diag(inst.distance), np.zeros(inst.num_nodes))


def test_malformed_r1_file_rejected(tmp_path):
    bad = tmp_path / "bad.sd"
    bad.write_text("2 100\n10\n0 0\n1 1\n2 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="demand line"):
        loader.load(bad, variant="SDVRP")
