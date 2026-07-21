"""SDVRP experiment and report metadata migration tests."""

from pathlib import Path

import yaml


NEW_SOLVERS = ["aasa_pyvrp", "aasa_vroom", "alkaid_sdvrp"]
OLD_SOLVERS = ["sdvrp_tabu", "sdvrp_pyvrp", "sdvrp_ortools", "sdvrp_vroom"]


def _load(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _cells(config: dict) -> int:
    instances = sum(len(group["instances"]) for group in config["datasets"])
    return instances * len(config["solvers"]) * len(config["seeds"])


def test_sdvrp_configs_use_new_solvers_and_uncontaminated_run_ids():
    smoke = _load("experiments/sdvrp_smoke.yaml")
    full = _load("experiments/sdvrp_benchmark.yaml")

    assert smoke["solvers"] == NEW_SOLVERS
    assert full["solvers"] == NEW_SOLVERS
    assert smoke["run_id"] != "sdvrp_r1_smoke"
    assert full["run_id"] != "sdvrp_r1_benchmark"
    assert _cells(smoke) == 24
    assert _cells(full) == 2850


def test_report_and_aggregation_metadata_have_no_obsolete_methods():
    aggregate = Path("scripts/aggregate.py").read_text(encoding="utf-8")
    report = Path("scripts/generate_report.py").read_text(encoding="utf-8")
    for solver in NEW_SOLVERS:
        assert solver in aggregate
        assert solver in report
    for solver in OLD_SOLVERS:
        assert solver not in aggregate
        assert solver not in report
