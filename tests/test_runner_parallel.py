"""Parallel execution (``--threads N``) must produce the same cells as sequential.

We assert the *set* of (instance, solver, seed) rows and their statuses match a
sequential run — not exact objectives, since time-budgeted solvers may vary
slightly run-to-run.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from vrpbench.runner.config import load_config
from vrpbench.runner.run import run_experiment

DATA = Path(__file__).parent / "data"


def _config(tmp_path: Path, results_dir: Path) -> Path:
    body = (
        "run_id: par\n"
        "seeds: [0, 1]\n"  # 2 seeds x 2 solvers x 1 instance = 4 cells
        "time_budget:\n  base_s: 1\n  per_node_ms: 0\n"
        f"results_dir: '{results_dir.as_posix()}'\n"
        "bks_path: 'data/bks.csv'\n"
        "solvers: [pyvrp, ortools]\n"
        "datasets:\n"
        "  - variant: CVRP\n"
        f"    instances: ['{(DATA / 'toy.vrp').as_posix()}']\n"
    )
    p = tmp_path / "exp.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def _row_keys(results_dir: Path) -> set[tuple[str, str, str]]:
    with (results_dir / "results.csv").open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        assert row["status"] == "ok", row
        assert float(row["obj_mismatch"]) == pytest.approx(0.0, abs=1e-6)
    return {(r["instance_name"], r["solver"], r["seed"]) for r in rows}


def test_threads_rejects_zero(tmp_path):
    cfg = load_config(_config(tmp_path, tmp_path / "r"))
    with pytest.raises(ValueError, match="threads must be >= 1"):
        run_experiment(cfg, threads=0)


def test_parallel_matches_sequential(tmp_path):
    seq_dir = tmp_path / "seq"
    par_dir = tmp_path / "par"

    seq_failures = run_experiment(load_config(_config(tmp_path, seq_dir)), threads=1)
    par_failures = run_experiment(load_config(_config(tmp_path, par_dir)), threads=2)

    assert seq_failures == 0
    assert par_failures == 0

    seq_keys = _row_keys(seq_dir)
    par_keys = _row_keys(par_dir)

    assert len(seq_keys) == 4
    assert par_keys == seq_keys
