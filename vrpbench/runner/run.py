"""The benchmark execution loop.

Expands the experiment grid (instance x solver x seed) and solves each cell. By
default cells run sequentially (fair wall-clock timing on a single workstation);
passing ``threads > 1`` fans the cells out across that many worker *processes*
(see :func:`run_experiment`). Every solution is independently verified and
scored, and each result is appended incrementally. A failure in one cell is
captured and never aborts the batch.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from datetime import datetime, timezone
from pathlib import Path

from vrpbench.core import evaluate
from vrpbench.datasets import loader
from vrpbench.datasets.bks import load_bks
from vrpbench.results.store import ResultStore, RunRecord
from vrpbench.runner.config import ExperimentConfig
from vrpbench.solvers import get_solver


def run_experiment(cfg: ExperimentConfig, threads: int = 1, force: bool = False) -> int:
    """Run all cells; return the number of cells that did not finish 'ok'.

    ``threads`` is the number of parallel worker processes. ``threads == 1``
    (the default) keeps the original in-process sequential loop, byte-for-byte.
    ``threads > 1`` solves cells concurrently across a process pool — each cell
    is fully independent, so the only behavioural difference is that result rows
    land in completion order rather than grid order.

    Resume: unless ``force`` is set, cells already recorded in the results CSV
    (any status: ok / infeasible / error) are skipped, so an interrupted batch
    can be restarted without recomputing finished work.
    """
    if threads < 1:
        raise ValueError(f"threads must be >= 1, got {threads}")

    bks = load_bks(cfg.bks_path)
    store = ResultStore(cfg.results_dir, store_detail=cfg.store_detail)

    cells = [
        (group.variant, path, name, seed)
        for group in cfg.datasets
        for path in group.instances
        for name in cfg.solvers
        for seed in cfg.seeds
    ]

    total_grid = len(cells)
    if not force:
        done = store.load_done_keys()
        # Stem heuristic: instance_name == Path(path).stem (verified for all loaders/sets).
        cells = [c for c in cells if (Path(c[1]).stem, c[0], c[2], c[3]) not in done]
        skipped = total_grid - len(cells)
        print(
            f"Resume: {skipped}/{total_grid} cells already in {store.csv_path}; "
            f"running {len(cells)} remaining."
            + ("" if cells else " Nothing to do.")
        )
    else:
        print(f"--force: ignoring existing rows; running all {total_grid} cells.")

    total = len(cells)
    if total == 0:
        print(f"\nDone: 0/0 ok, results in {store.csv_path}")
        return 0

    if threads == 1:
        failures = _run_sequential(cfg, bks, store, cells, total)
    else:
        failures = _run_parallel(cfg, store, cells, total, threads)

    print(f"\nDone: {total - failures}/{total} ok, results in {store.csv_path}")
    return failures


def _run_sequential(cfg, bks, store, cells, total) -> int:
    """The original loop: one cell at a time, in grid order."""
    # Instantiate each solver once (cheap) and cache loaded instances by path.
    solver_cache = {name: get_solver(name) for name in cfg.solvers}
    instance_cache: dict[str, object] = {}

    failures = 0
    for idx, (variant, path, solver_name, seed) in enumerate(cells, start=1):
        record = _run_cell(
            cfg, bks, instance_cache, solver_cache, variant, path, solver_name, seed
        )
        store.append(record)
        if record.status != "ok":
            failures += 1
        _print_progress(idx, total, record)
    return failures


def _run_parallel(cfg, store, cells, total, threads) -> int:
    """Fan the cells out across ``threads`` worker processes.

    The main process stays the sole writer to the CSV and to stdout (no locks).
    A worker that raises is already handled inside :func:`_run_cell` (returns an
    ``error`` record); a *hard* worker crash surfaces as ``BrokenProcessPool``,
    which we record as an error cell so the batch still drains.
    """
    failures = 0
    with ProcessPoolExecutor(
        max_workers=threads, initializer=_worker_init, initargs=(cfg,)
    ) as ex:
        futures = {ex.submit(_solve_cell_worker, cell): cell for cell in cells}
        for idx, fut in enumerate(as_completed(futures), start=1):
            cell = futures[fut]
            try:
                record = fut.result()
            except BrokenProcessPool as exc:  # a worker died hard (e.g. segfault)
                record = _error_record(cfg, cell, f"{type(exc).__name__}: {exc}")
            store.append(record)
            if record.status != "ok":
                failures += 1
            _print_progress(idx, total, record)
    return failures


# --- Worker-process state (parallel path) --------------------------------------
# Populated once per worker by ``_worker_init`` so cfg/bks are not re-pickled per
# task and the instance/solver caches are reused across a worker's cells.
_WORKER_STATE: dict[str, object] = {}


def _worker_init(cfg: ExperimentConfig) -> None:
    _WORKER_STATE["cfg"] = cfg
    _WORKER_STATE["bks"] = load_bks(cfg.bks_path)
    _WORKER_STATE["instance_cache"] = {}
    _WORKER_STATE["solver_cache"] = {}


def _solve_cell_worker(cell) -> RunRecord:
    variant, path, solver_name, seed = cell
    s = _WORKER_STATE
    return _run_cell(
        s["cfg"], s["bks"], s["instance_cache"], s["solver_cache"],
        variant, path, solver_name, seed,
    )


# --- Shared scoring path (used by both sequential and parallel) ----------------
def _run_cell(
    cfg, bks, instance_cache, solver_cache, variant, path, solver_name, seed
) -> RunRecord:
    solver = _cached_solver(solver_cache, solver_name)
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


def _cached_solver(solver_cache, name):
    solver = solver_cache.get(name)
    if solver is None:
        solver = get_solver(name)
        solver_cache[name] = solver
    return solver


def _error_record(cfg, cell, message: str) -> RunRecord:
    """Minimal error record for a cell whose worker died before returning."""
    variant, path, solver_name, seed = cell
    return RunRecord(
        run_id=cfg.run_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        instance_name=path,
        variant=variant,
        solver=solver_name,
        solver_version="unknown",
        seed=seed,
        time_budget_s=0.0,
        status="error",
        error=message,
    )


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
