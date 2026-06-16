"""The benchmark execution loop.

Expands the experiment grid (instance x solver x seed), solves each cell
sequentially (fair wall-clock timing on a single workstation), independently
verifies and scores every solution, and appends each result incrementally.
A failure in one cell is captured and never aborts the batch.
"""

from __future__ import annotations

from datetime import datetime, timezone

from vrpbench.core import evaluate
from vrpbench.datasets import loader
from vrpbench.datasets.bks import load_bks
from vrpbench.results.store import ResultStore, RunRecord
from vrpbench.runner.config import ExperimentConfig
from vrpbench.solvers import get_solver


def run_experiment(cfg: ExperimentConfig) -> int:
    """Run all cells; return the number of cells that did not finish 'ok'."""
    bks = load_bks(cfg.bks_path)
    store = ResultStore(cfg.results_dir, store_detail=cfg.store_detail)

    # Instantiate each solver once (cheap) and cache loaded instances by path.
    solvers = {name: get_solver(name) for name in cfg.solvers}
    instance_cache: dict[str, object] = {}

    cells = [
        (group.variant, path, name, seed)
        for group in cfg.datasets
        for path in group.instances
        for name in cfg.solvers
        for seed in cfg.seeds
    ]

    failures = 0
    total = len(cells)
    for idx, (variant, path, solver_name, seed) in enumerate(cells, start=1):
        solver = solvers[solver_name]
        record = _run_cell(cfg, bks, instance_cache, variant, path, solver, seed)
        store.append(record)
        if record.status != "ok":
            failures += 1
        _print_progress(idx, total, record)

    print(f"\nDone: {total - failures}/{total} ok, results in {store.csv_path}")
    return failures


def _run_cell(cfg, bks, instance_cache, variant, path, solver, seed) -> RunRecord:
    timestamp = datetime.now(timezone.utc).isoformat()
    base = dict(
        run_id=cfg.run_id,
        timestamp=timestamp,
        instance_name=path,  # replaced with parsed name on success
        variant=variant,
        solver=solver.name,
        solver_version=_safe_version(solver),
        seed=seed,
        time_budget_s=0.0,
    )
    try:
        instance = instance_cache.get(path)
        if instance is None:
            instance = loader.load(path, variant=variant)
            instance_cache[path] = instance
        base["instance_name"] = instance.name

        budget = cfg.time_budget.resolve(instance.num_nodes)
        base["time_budget_s"] = budget

        solution = solver.solve(instance, time_budget_s=budget, seed=seed)
        ev = evaluate.verify(instance, solution)
        bks_value = bks.lookup(instance.name)
        gap = evaluate.gap(ev.objective, bks_value)

        return RunRecord(
            **base,
            status="ok" if ev.feasible else "infeasible",
            objective=ev.objective,
            bks_value=bks_value,
            gap_pct=gap,
            feasible=ev.feasible,
            runtime_s=solution.runtime_s,
            num_vehicles=ev.num_vehicles,
            solver_objective=solution.objective,
            obj_mismatch=ev.obj_mismatch,
            routes=solution.routes,
            error="" if ev.feasible else "; ".join(ev.violations),
        )
    except Exception as exc:  # never abort the batch
        return RunRecord(**base, status="error", error=f"{type(exc).__name__}: {exc}")


def _print_progress(idx: int, total: int, record: RunRecord) -> None:
    obj = "-" if record.objective is None else f"{record.objective:.2f}"
    gap = "-" if record.gap_pct is None else f"{record.gap_pct:+.2f}%"
    rt = "-" if record.runtime_s is None else f"{record.runtime_s:.1f}s"
    print(
        f"[{idx}/{total}] {record.instance_name} | {record.solver} "
        f"seed={record.seed} | {record.status} | obj={obj} gap={gap} t={rt}"
    )


def _safe_version(solver) -> str:
    try:
        return solver.version()
    except Exception:  # pragma: no cover
        return "unknown"
