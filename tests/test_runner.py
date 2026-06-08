"""Tests for config parsing and the end-to-end runner (Step 7)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from vrpbench.runner.config import load_config
from vrpbench.runner.run import run_experiment

DATA = Path(__file__).parent / "data"


def _write_config(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "exp.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def test_config_rejects_unknown_solver(tmp_path):
    cfg = _write_config(
        tmp_path,
        "solvers: [nope]\ndatasets:\n  - variant: CVRP\n    instances: []\n",
    )
    with pytest.raises(ValueError, match="unknown solver"):
        load_config(cfg)


def test_config_accepts_ortools_vrptw(tmp_path):
    # After Step 8 the OR-Tools adapter supports VRPTW.
    body = (
        "solvers: [ortools]\n"
        "datasets:\n"
        "  - variant: VRPTW\n"
        f"    instances: ['{(DATA / 'toy_solomon.txt').as_posix()}']\n"
    )
    cfg = load_config(_write_config(tmp_path, body))
    assert cfg.solvers == ["ortools"]


def test_config_rejects_missing_instance(tmp_path):
    body = (
        "solvers: [pyvrp]\n"
        "datasets:\n  - variant: CVRP\n    instances: ['does/not/exist.vrp']\n"
    )
    with pytest.raises(ValueError, match="not found"):
        load_config(_write_config(tmp_path, body))


def test_end_to_end_run(tmp_path):
    results_dir = tmp_path / "results"
    body = (
        "run_id: test\n"
        "seeds: [0]\n"
        "time_budget:\n  base_s: 1\n  per_node_ms: 0\n"
        f"results_dir: '{results_dir.as_posix()}'\n"
        "bks_path: 'data/bks.csv'\n"
        "solvers: [pyvrp, ortools]\n"
        "datasets:\n"
        "  - variant: CVRP\n"
        f"    instances: ['{(DATA / 'toy.vrp').as_posix()}']\n"
    )
    cfg = load_config(_write_config(tmp_path, body))
    failures = run_experiment(cfg)
    assert failures == 0

    with (results_dir / "results.csv").open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    # 2 solvers x 1 instance x 1 seed
    assert len(rows) == 2
    for row in rows:
        assert row["status"] == "ok"
        assert row["feasible"] == "True"
        assert float(row["objective"]) == pytest.approx(8.0)
        assert float(row["obj_mismatch"]) == pytest.approx(0.0, abs=1e-6)
