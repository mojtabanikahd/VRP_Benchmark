# vrpbench

A fast, reproducible benchmarking harness for **CVRP** and **VRPTW** that compares
complete solvers on *final solution quality + runtime* only.

Bundled solvers: **PyVRP** (CVRP + VRPTW) and **OR-Tools** (CVRP + VRPTW). A future
custom solver plugs in as one adapter file + one registry entry.

## Install

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run a benchmark

```powershell
.venv\Scripts\python.exe -m vrpbench.cli --config experiments/smoke.yaml
```

Results are appended incrementally to `results/results.csv` (one row per run).

## Experiment config (YAML)

```yaml
run_id: baseline          # optional; default = timestamp
seeds: [0, 1, 2]          # one run per seed
time_budget:
  base_s: 10              # wall-clock budget per instance ...
  per_node_ms: 0          # ... + this many ms per node (0 = flat budget)
solvers: [pyvrp, ortools]
store_detail: false       # also dump per-run JSON (routes + metadata)
datasets:
  - variant: CVRP
    instances:
      - data/instances/X-n101-k25.vrp
  - variant: VRPTW
    instances:
      - data/instances/C101.txt
```

## Layout

| Module | Responsibility |
|---|---|
| `vrpbench/core` | `Instance`, `Solution`, independent `evaluate` (objective recompute, feasibility, gap) |
| `vrpbench/datasets` | `loader` (CVRPLIB `.vrp` + Solomon/GH `.txt` via `vrplib`), curated `bks` table |
| `vrpbench/solvers` | `Solver` protocol + `pyvrp` / `ortools` adapters + `SOLVERS` registry |
| `vrpbench/runner` | YAML `config` + execution loop |
| `vrpbench/results` | incremental CSV store (+ optional per-run JSON) |

## Datasets & BKS

Place instance files under `data/instances/`:

- **CVRP** — CVRPLIB X-set (`.vrp`, EUC_2D, integer-rounded distances).
- **VRPTW** — Solomon + Gehring-Homberger (`.txt`, float Euclidean distances).

`data/bks.csv` (`instance_name, variant, bks_value, rounding, source`) holds curated
best-known values for gap computation. The `rounding` column documents the distance
convention each BKS was computed under (`int` for CVRP, `float`/1-decimal for VRPTW),
kept consistent with the loader. Missing BKS → `gap_pct` is left blank, not an error.

## Correctness model

Every solution is **independently re-scored** against the instance's authoritative
distance matrix and re-checked for feasibility (visiting, capacity, time windows).
The `obj_mismatch` column flags any disagreement between a solver's reported objective
and our recomputation (≈0 for CVRP; tiny for VRPTW due to the solver's ×10 integer
rounding).

## Tests

```powershell
.venv\Scripts\python.exe -m pytest -q
```
