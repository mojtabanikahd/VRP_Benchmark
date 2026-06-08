"""Tests for the results store (Step 6)."""

from __future__ import annotations

import csv
import json

from vrpbench.results.store import ResultStore, RunRecord


def _record(**kw) -> RunRecord:
    base = dict(
        run_id="r1",
        timestamp="2026-06-07T00:00:00",
        instance_name="toy",
        variant="CVRP",
        solver="pyvrp",
        seed=0,
        time_budget_s=1.0,
        status="ok",
        objective=8.0,
        bks_value=8.0,
        gap_pct=0.0,
        feasible=True,
        runtime_s=0.5,
        num_vehicles=2,
    )
    base.update(kw)
    return RunRecord(**base)


def test_append_writes_header_once(tmp_path):
    store = ResultStore(tmp_path)
    store.append(_record(seed=0))
    store.append(_record(seed=1))

    with (tmp_path / "results.csv").open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2
    assert rows[0]["solver"] == "pyvrp"
    assert rows[1]["seed"] == "1"
    # header appears exactly once
    text = (tmp_path / "results.csv").read_text()
    assert text.count("instance_name") == 1


def test_resume_appends_without_duplicate_header(tmp_path):
    ResultStore(tmp_path).append(_record(seed=0))
    ResultStore(tmp_path).append(_record(seed=1))  # fresh store, existing file
    text = (tmp_path / "results.csv").read_text()
    assert text.count("instance_name") == 1


def test_detail_json_written(tmp_path):
    store = ResultStore(tmp_path, store_detail=True)
    store.append(_record(routes=[[1, 2], [3]]))
    files = list((tmp_path / "runs").glob("*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text())
    assert payload["routes"] == [[1, 2], [3]]
