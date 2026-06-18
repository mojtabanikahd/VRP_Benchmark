"""Parse and validate an experiment YAML into typed objects.

Validation is strict and fail-fast: unknown solvers, missing instance files, and
solver/variant mismatches (e.g. OR-Tools + VRPTW before Step 8) raise clear
errors before any solving begins.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

from vrpbench.core.instance import MDVRP, PVRP, VARIANTS
from vrpbench.datasets.loader import detect_format
from vrpbench.solvers import SOLVERS, get_solver


@dataclass(frozen=True)
class TimeBudget:
    base_s: float = 10.0
    per_node_ms: float = 0.0

    def resolve(self, num_nodes: int) -> float:
        return self.base_s + (self.per_node_ms / 1000.0) * num_nodes


@dataclass(frozen=True)
class DatasetGroup:
    variant: str
    instances: list[str]


@dataclass(frozen=True)
class ExperimentConfig:
    run_id: str
    seeds: list[int]
    solvers: list[str]
    datasets: list[DatasetGroup]
    time_budget: TimeBudget = field(default_factory=TimeBudget)
    store_detail: bool = False
    results_dir: str = "results"
    bks_path: str = "data/bks.csv"


def load_config(path: str | os.PathLike) -> ExperimentConfig:
    with Path(path).open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    run_id = str(raw.get("run_id") or datetime.now().strftime("run_%Y%m%d_%H%M%S"))
    seeds = [int(s) for s in raw.get("seeds", [0])]
    solvers = [str(s) for s in raw.get("solvers", [])]

    tb_raw = raw.get("time_budget", {}) or {}
    time_budget = TimeBudget(
        base_s=float(tb_raw.get("base_s", 10.0)),
        per_node_ms=float(tb_raw.get("per_node_ms", 0.0)),
    )

    datasets = [
        DatasetGroup(
            variant=str(group["variant"]),
            instances=[str(p) for p in group.get("instances", [])],
        )
        for group in raw.get("datasets", [])
    ]

    cfg = ExperimentConfig(
        run_id=run_id,
        seeds=seeds,
        solvers=solvers,
        datasets=datasets,
        time_budget=time_budget,
        store_detail=bool(raw.get("store_detail", False)),
        results_dir=str(raw.get("results_dir", "results")),
        bks_path=str(raw.get("bks_path", "data/bks.csv")),
    )
    _validate(cfg)
    return cfg


def _validate(cfg: ExperimentConfig) -> None:
    if not cfg.solvers:
        raise ValueError("config: 'solvers' must list at least one solver")
    for name in cfg.solvers:
        if name not in SOLVERS:
            raise ValueError(f"config: unknown solver {name!r}; available {sorted(SOLVERS)}")
    if not cfg.datasets:
        raise ValueError("config: 'datasets' must list at least one group")
    if cfg.time_budget.base_s < 0 or cfg.time_budget.per_node_ms < 0:
        raise ValueError("config: time budget values must be non-negative")

    # Resolve solver capabilities once for variant checks.
    capabilities = {name: get_solver(name).supported_variants for name in cfg.solvers}

    for group in cfg.datasets:
        if group.variant not in VARIANTS:
            raise ValueError(f"config: unknown variant {group.variant!r}")
        for inst_path in group.instances:
            p = Path(inst_path)
            if not p.exists():
                raise ValueError(f"config: instance file not found: {inst_path}")
            # MDVRP and PVRP share the .txt extension with Solomon VRPTW, so they
            # cannot be inferred from the file; the declared variant is authoritative.
            if group.variant not in (MDVRP, PVRP):
                _, detected = detect_format(inst_path)
                if detected != group.variant:
                    raise ValueError(
                        f"config: {inst_path} looks like {detected} "
                        f"but is declared under {group.variant}"
                    )
        # Every chosen solver must support this group's variant.
        for name in cfg.solvers:
            if group.variant not in capabilities[name]:
                raise ValueError(
                    f"config: solver {name!r} does not support {group.variant} "
                    f"(supports {capabilities[name]})"
                )
