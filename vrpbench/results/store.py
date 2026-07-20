"""Incremental results storage.

Primary output is a flat, analysis-ready CSV (one row per run), written
incrementally so a mid-batch crash loses nothing. An optional per-run JSON dump
(full routes + metadata) enables exact reproduction when ``store_detail`` is on.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Column order for results.csv (also the canonical RunRecord field order).
FIELDNAMES = [
    "run_id",
    "timestamp",
    "instance_name",
    "variant",
    "solver",
    "solver_version",
    "seed",
    "time_budget_s",
    "status",
    "objective",
    "bks_value",
    "gap_pct",
    "feasible",
    "runtime_s",
    "num_vehicles",
    "solver_objective",
    "obj_mismatch",
    "error",
]


@dataclass
class RunRecord:
    run_id: str
    timestamp: str
    instance_name: str
    variant: str
    solver: str
    seed: int
    time_budget_s: float
    status: str  # "ok" | "error" | "infeasible" | "timeout"
    solver_version: str = ""
    objective: float | None = None
    bks_value: float | None = None
    gap_pct: float | None = None
    feasible: bool | None = None
    runtime_s: float | None = None
    num_vehicles: int | None = None
    solver_objective: float | None = None
    obj_mismatch: float | None = None
    error: str = ""
    # Detail-only (not written to CSV):
    routes: list[list[int]] = field(default_factory=list)
    route_deliveries: list[dict[int, int]] = field(default_factory=list)

    def csv_row(self) -> dict:
        d = asdict(self)
        d.pop("routes", None)
        d.pop("route_deliveries", None)
        return {k: d[k] for k in FIELDNAMES}


class ResultStore:
    def __init__(self, results_dir: str | Path = "results", store_detail: bool = False):
        self.dir = Path(results_dir)
        self.csv_path = self.dir / "results.csv"
        self.runs_dir = self.dir / "runs"
        self.store_detail = store_detail
        self._header_written = self.csv_path.exists()

    def load_done_keys(self, run_id: str) -> frozenset[tuple[str, str, str, str, int]]:
        """Return (run_id, instance_name, variant, solver, seed) for every row in the CSV.

        Status-agnostic: ok / infeasible / error all count as done. A malformed row
        (missing column or non-int seed) is skipped, so that cell will be re-run.
        Scoped to run_id so results from a different experiment never block this one.
        """
        if not self.csv_path.exists():
            return frozenset()
        done: set[tuple[str, str, str, str, int]] = set()
        with self.csv_path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                try:
                    if row["run_id"] == run_id:
                        done.add((
                            row["run_id"],
                            row["instance_name"],
                            row["variant"],
                            row["solver"],
                            int(row["seed"]),
                        ))
                except (KeyError, ValueError):
                    pass  # malformed row -> treat cell as not-done (safe: re-run it)
        return frozenset(done)

    def _ensure_dirs(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        if self.store_detail:
            self.runs_dir.mkdir(parents=True, exist_ok=True)

    def append(self, record: RunRecord) -> None:
        self._ensure_dirs()
        write_header = not self._header_written
        with self.csv_path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
            if write_header:
                writer.writeheader()
                self._header_written = True
            writer.writerow(record.csv_row())

        if self.store_detail:
            self._write_detail(record)

    def _write_detail(self, record: RunRecord) -> None:
        safe_inst = record.instance_name.replace("/", "_").replace("\\", "_")
        fname = f"{record.run_id}__{safe_inst}__{record.solver}__seed{record.seed}.json"
        payload = asdict(record)
        with (self.runs_dir / fname).open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
