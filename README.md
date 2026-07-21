# vrpbench

A fast, reproducible benchmarking harness for **CVRP**, **VRPTW**, **MDVRP**
(multi-depot), **VRPMPD** (mixed pickup & delivery), **PVRP** (periodic VRP), and
**SDVRP** (Split Delivery VRP) that compares complete solvers on *final
solution quality + runtime* only.

Bundled solvers: **PyVRP** (CVRP + VRPTW + MDVRP + VRPMPD), **OR-Tools** (CVRP + VRPTW +
MDVRP + VRPMPD), **VROOM** (CVRP + VRPTW + MDVRP + VRPMPD), **VRPSolverEasy** (CVRP +
VRPTW â€” exact BCP via BaPCod; MDVRP, VRPMPD, PVRP, and SDVRP not supported), **PVRPSolver**
wrapping any of the three heuristic solvers (`pvrp_pyvrp`, `pvrp_ortools`, `pvrp_vroom`)
for PVRP via ALNS over day-combination assignments, plus **AASA-PyVRP**,
**AASA-VROOM**, and the externally provisioned **Alkaid-SDVRP** executable for
SDVRP. A future custom solver plugs in as one adapter file + one registry entry.

## Install

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements.txt` contains a single `-e .[dev]` line, so pip installs the
`vrpbench` package in editable mode together with all runtime and development
dependencies declared in `pyproject.toml`. `pyproject.toml` is the single
source of truth for dependencies; `requirements.txt` is just the install
entry-point.

> **VRPSolverEasy (exact solver):** the pip package does not bundle the BaPCod shared
> library. See [BAPCOD_SETUP.md](BAPCOD_SETUP.md) for the one-time binary copy step
> required before `vrpsolvereasy` cells will run.

## Run a benchmark

```powershell
# Quick smoke test â€” PyVRP + OR-Tools on one CVRP and one VRPTW instance
.venv\Scripts\python.exe -m vrpbench.cli --config experiments/smoke.yaml

# MDVRP smoke â€” PyVRP + OR-Tools + VROOM on small Cordeau multi-depot instances
.venv\Scripts\python.exe -m vrpbench.cli --config experiments/mdvrp_smoke.yaml

# VRPMPD smoke â€” PyVRP + OR-Tools + VROOM on two Salhi-Nagy S instances
.venv\Scripts\python.exe -m vrpbench.cli --config experiments/vrpmpd_smoke.yaml

# PVRP smoke â€” three PVRP wrappers on one old (no duration limit) + one new (duration limit) instance
.venv\Scripts\python.exe -m vrpbench.cli --config experiments/pvrp_smoke.yaml

# SDVRP smoke - two AASA reductions and native Alkaid on representative R1 instances
.venv\Scripts\python.exe -m vrpbench.cli --config experiments/sdvrp_smoke.yaml

# Full benchmark â€” all four solvers on the standard CVRP X-set + Solomon VRPTW set
.venv\Scripts\python.exe -m vrpbench.cli --config experiments/benchmark.yaml

# Run cells in parallel across 4 worker processes (~4Ã— faster on a 4-core machine)
.venv\Scripts\python.exe -m vrpbench.cli --config experiments/sdvrp_smoke.yaml --threads 4
```

Results are appended incrementally to `results/results.csv` (one row per run). Re-running
the same config **resumes** by default: cells already in the CSV are skipped (see below).

### Running all benchmarks (Linux)

`run_all_benchmarks.sh` runs all five full-benchmark configs sequentially â€” CVRP/VRPTW,
VRPMPD, SDVRP, PVRP, and MDVRP â€” in a single invocation. Because every config appends to
the same `results/results.csv`, the configs must run sequentially; `--threads` controls
intra-experiment parallelism (cells within one config solved concurrently).

```bash
# One-time: make the script executable (required after cloning on Linux/macOS)
chmod +x run_all_benchmarks.sh

# Use all available cores (detected via nproc)
./run_all_benchmarks.sh

# Explicit thread count
./run_all_benchmarks.sh --threads 8

# Re-run every cell, ignoring previously recorded results
./run_all_benchmarks.sh --force

# Both flags together
./run_all_benchmarks.sh --threads 8 --force
```

The script auto-detects the Python interpreter (`.venv/bin/python` â†’ `python3` â†’ `python`),
prints a timestamped header per config, and exits non-zero if any config fails (listing
which ones).

### Resume (skip already-done cells)

Every run reads `results/results.csv` at startup and skips any cell already recorded there,
so an interrupted batch can simply be re-launched to finish the remaining work â€” no
recomputation of finished cells.

```powershell
# First launch solves the whole grid; if interrupted, just run the same command again â€”
# it picks up only the cells that have no row yet.
.venv\Scripts\python.exe -m vrpbench.cli --config experiments/benchmark.yaml --threads 8

# Force a full re-run, ignoring existing rows (--no-resume is an alias):
.venv\Scripts\python.exe -m vrpbench.cli --config experiments/benchmark.yaml --force
```

- A cell is identified by `(run_id, instance_name, variant, solver, seed)` â€” `solver_version`
  and `time_budget_s` are **not** part of the key. Results from a different `run_id` never
  block cells in the current experiment.
- A cell counts as done if it has **any** row (`ok`, `infeasible`, **or `error`**). To retry
  an `error` cell, re-run with `--force` or delete its row from the CSV.
- The startup line reports what was skipped, e.g.
  `Resume: 1430/1600 cells already in results/results.csv; running 170 remaining.`
- `--force` (alias `--no-resume`) **appends** a fresh set of rows; it does not truncate the
  CSV. To start completely clean, point `results_dir` at a new folder or delete the CSV.

### Parallel execution (`--threads N`)

The experiment grid (`instance Ã— solver Ã— seed`) is **embarrassingly parallel**: each cell is
independent. Pass `--threads N` (alias `-j N`) to run up to `N` cells simultaneously across
worker processes, cutting wall-clock time roughly NÃ— on a multi-core machine.

```powershell
.venv\Scripts\python.exe -m vrpbench.cli --config experiments/benchmark.yaml --threads 8
```

- **Default is `--threads 1`** â€” the original sequential loop, byte-identical to previous behaviour.
- The time budget per cell is **unchanged**: each worker runs on its own core and receives the
  full `time_budget_s`. Keep `N â‰¤ physical cores` to avoid contention (the CLI warns if you exceed `os.cpu_count()`).
- Result rows land in the CSV in **completion order** (not grid order) when `N > 1`; the set of
  rows is identical to a sequential run.
- A solve exception in one cell is captured as `status=error` and never aborts the batch â€”
  the same guarantee as the sequential mode.

## Reporting (DOCX)

Two standalone scripts under `scripts/` turn `results/results.csv` into a formatted Word
report comparing every solver across all six variants:

1. `scripts/aggregate.py` reads `results/results.csv` and writes `results/table_data.json`,
   reducing each `(instance, solver)` cell over its seeds to the mean objective, gap (CVRP
   only), runtime, and vehicle count over the `ok` runs, plus an `n_ok/n_total` success
   string. Instance names are normalised (path/extension stripped) so the clean and
   path-form duplicates a resumed run can leave in the CSV merge into one row.
2. `scripts/generate_report.py` reads that JSON and writes
   `results/vrp_benchmark_report.docx`.

Reporting needs **`python-docx`** (`pandas` is already a harness dependency):

```powershell
.venv\Scripts\python.exe -m pip install python-docx
.venv\Scripts\python.exe scripts/aggregate.py
.venv\Scripts\python.exe scripts/generate_report.py
```

The report is one **landscape-A4 table per variant** (CVRP, VRPTW, MDVRP, VRPMPD, SDVRP,
PVRP) preceded by a cover page. Each table groups its columns by solver, and the grouping
is made visually explicit:

- **Thick navy group-boundary lines** separate each solver's column block (and the
  *Instance Features* block) from its neighbours, while thin gray lines divide the metric
  columns *inside* a block.
- **Per-solver colour coding** in the header bands â€” each solver keeps a consistent hue
  across every table (PyVRP = blue, OR-Tools = orange, VROOM = green, VRPSolverEasy =
  purple, Tabu Search = red).
- **Best-value highlighting** â€” in each row the minimum of every comparable metric
  (objective, gap, time, vehicles) is shown in bold, shaded with a lighter tint of that
  solver's group colour. An em-dash (`â€”`) marks cells with no successful run, and the
  `Success` column reports successful runs out of the seed count.

Re-run `aggregate.py` then `generate_report.py` whenever `results/results.csv` changes;
both outputs land in `results/`.

## Experiment config (YAML)

```yaml
run_id: baseline          # optional; default = timestamp
seeds: [0, 1, 2]          # one run per seed
time_budget:
  base_s: 10              # wall-clock budget per instance ...
  per_node_ms: 0          # ... + this many ms per node (0 = flat budget)
solvers: [pyvrp, ortools, vroom, vrpsolvereasy]
store_detail: false       # also dump per-run JSON (routes + metadata)
datasets:
  - variant: CVRP
    instances:
      - data/instances/X/X-n101-k25.vrp
  - variant: VRPTW
    instances:
      - data/instances/Solomon/C101.txt
  - variant: MDVRP            # multi-depot; must be declared explicitly (see note)
    instances:
      - data/instances/MDVRP/old/p01.txt
  - variant: VRPMPD           # mixed pickup & delivery; inferred from .vrpmpd extension
    instances:
      - data/instances/S/CMT01H.vrpmpd
  - variant: PVRP             # periodic VRP; must be declared explicitly (see note)
    instances:
      - data/instances/PVRP/old/p01.txt
  - variant: SDVRP            # Split Delivery VRP R1
    instances:
      - data/instances/SDVRP_R1_instances/SET-1/SD1.txt
```

> **MDVRP and PVRP files share the `.txt` extension with Solomon VRPTW**, so declare
> `variant: MDVRP` or `variant: PVRP` explicitly. SDVRP R1 is detected from `.sd`, `.cri`,
> or R1-shaped `.txt` files, and explicit `variant: SDVRP` is also accepted.
> `vrpsolvereasy` cannot be listed under an MDVRP, VRPMPD, PVRP, or SDVRP group (config
> validation rejects it with a clear error). PVRP solvers must use the `pvrp_*` names
> (`pvrp_pyvrp`, `pvrp_ortools`, `pvrp_vroom`) and SDVRP solvers must use
> `aasa_pyvrp`, `aasa_vroom`, or `alkaid_sdvrp`; the plain
> `pyvrp`/`ortools`/`vroom` names do not support PVRP or SDVRP.
>
> **VRPMPD files use the unique `.vrpmpd` extension** â€” the variant is inferred automatically
> and no explicit `variant:` declaration is needed (though it is accepted and validated).

## Layout

| Module | Responsibility |
|---|---|
| `vrpbench/core` | `Instance`, `Solution`, independent `evaluate` (objective recompute, feasibility, gap) |
| `vrpbench/datasets` | `loader` (CVRPLIB `.vrp` + Solomon/GH `.txt` via `vrplib`, Cordeau MDVRP/PVRP `.txt`, DIMACS SDVRP R1 `.txt`/`.sd`/`.cri`, Salhi-Nagy `.vrpmpd`), curated `bks` table |
| `vrpbench/solvers` | `Solver` protocol + `pyvrp` / `ortools` / `vroom` / `vrpsolvereasy` adapters + `pvrp_solver` ALNS wrapper + shared `aasa_solver` + external `alkaid_solver` + `SOLVERS` registry |
| `vrpbench/runner` | YAML `config` + execution loop (parallel `--threads`, resume / `--force`) |
| `vrpbench/results` | incremental CSV store (+ optional per-run JSON) |

## Solvers

| Name | Type | CVRP | VRPTW | MDVRP | VRPMPD | PVRP | SDVRP | Notes |
|---|---|---|---|---|---|---|---|---|
| `pyvrp` | Heuristic (LNS) | âœ“ | âœ“ | âœ“ | âœ“ | âœ— | âœ— | |
| `ortools` | Heuristic (CP-SAT/LNS) | âœ“ | âœ“ | âœ“ | âœ“ | âœ— | âœ— | |
| `vroom` | Heuristic (LNS) | âœ“ | âœ“ | âœ“ | âœ“ | âœ— | âœ— | Windows: numpy `uintc` workaround applied |
| `vrpsolvereasy` | Exact (BCP / BaPCod) | âœ“ | âœ“ | âœ— | âœ— | âœ— | âœ— | Requires BaPCod binaries; â‰¤ 1022 nodes; needs long time budgets (see below) |
| `pvrp_pyvrp` | ALNS wrapper (PyVRP inner) | âœ— | âœ— | âœ— | âœ— | âœ“ | âœ— | |
| `pvrp_ortools` | ALNS wrapper (OR-Tools inner) | âœ— | âœ— | âœ— | âœ— | âœ“ | âœ— | |
| `pvrp_vroom` | ALNS wrapper (VROOM inner) | âœ— | âœ— | âœ— | âœ— | âœ“ | âœ— | |
| `aasa_pyvrp` | AASA reduction + PyVRP | âœ— | âœ— | âœ— | âœ— | âœ— | âœ“ | Fixed `p=2`, two-level demand discretisation |
| `aasa_vroom` | AASA reduction + VROOM | âœ— | âœ— | âœ— | âœ— | âœ— | âœ“ | VROOM currently ignores `seed` |
| `alkaid_sdvrp` | Native Alkaid-SDVRP ILS/RVND | âœ— | âœ— | âœ— | âœ— | âœ— | âœ“ | Requires external v1.1 executable; see `ALKAID_SETUP.md` |

All three heuristic solvers handle multiple depots **natively** (PyVRP per-depot vehicle
types, OR-Tools per-vehicle `starts`/`ends`, VROOM per-vehicle `start`/`end`). MDVRP uses
classic *open* depot assignment â€” the solver chooses which depot serves each customer.

For **VRPMPD**, PyVRP and VROOM enforce the position-dependent load constraint natively
(each `Client`/`Job` carries both `delivery` and `pickup` amounts). OR-Tools uses a
two-dimension model (`Deliveries` + `Load` dimensions linked per vehicle) to replicate
the same constraint. All three use a large per-vehicle fixed cost to implement the
lexicographic two-stage objective (minimize vehicles first, then distance).

For **PVRP**, none of the base solvers natively support periodic routing, so all three are
driven through a shared `PVRPSolver` ALNS wrapper. The outer loop searches over
per-customer day-combination assignments (bitmasks encoding which of the `t` days each
customer is visited); for each candidate assignment the inner base solver routes each day
independently as a CVRP (old dataset, no duration limit) or VRPTW (new dataset, with a
per-route duration limit) sub-instance with a hard fleet cap of `m` vehicles/day. The
reported objective is the total travel distance summed across all `t` days; day-route
solutions are re-evaluated against the authoritative distance matrix so `obj_mismatch â‰ˆ 0`.

For **SDVRP**, the harness targets the DIMACS R1 Split Delivery VRP benchmark:
homogeneous capacity, explicit split-delivery quantities, no site-dependent vehicle
types, no route-duration fields, and no hard fleet cap. `aasa_pyvrp` and
`aasa_vroom` apply the A Priori Adaptive Splitting Algorithm with fixed `p=2` and
two distance levels, then solve the resulting colocated-fragment CVRP through the
existing adapters. This restricts delivered quantities to generated fragments and is
therefore an approximation of the full split space; these combinations are valid uses
of AASA's generic CVRP transformation, not reproductions of the paper's VRPH results.
`alkaid_sdvrp` passes the original R1 file directly to native Alkaid without AASA.
All decoded solutions carry `route_deliveries`, and objectives are recomputed from the
authoritative integer-rounded distance matrix so `obj_mismatch` is near zero.
## Datasets & BKS

Place instance files under `data/instances/`:

- **CVRP** â€” CVRPLIB X-set (`data/instances/X/`, `.vrp`, EUC_2D, integer-rounded
  distances). 150+ instances with BKS from Uchoa et al. 2017.
- **VRPTW** â€” Solomon benchmark (`data/instances/Solomon/`, `.txt`, float Euclidean
  distances). Complete 100-customer set (C1/C2/R1/R2/RC1/RC2 classes).
- **MDVRP** â€” Cordeau benchmark (`data/instances/MDVRP/`, `.txt`,
  [source](http://neumann.hec.ca/chairedistributique/data/)): `old/p01..p21` (integer
  coords) and `new/pr01..pr10` (float coords). Euclidean distances are nearest-integer
  rounded (matching the CVRP convention). The per-depot max-route-duration field is
  ignored (solved as capacity-constrained MDVRP); per-customer PVRP visit-frequency fields
  are discarded.
- **VRPMPD** â€” Salhiâ€“Nagy "S" benchmark (`data/instances/S/`, `.vrpmpd`,
  [source](http://webhotel4.ruc.dk/~keld/research/LKH-3/)): ~70 instances
  (`CMT01â€“CMT14` with `H/Q/T/X/Y` variants, 50â€“199 customers). Euclidean distances are
  nearest-integer rounded. Each customer is either a pure delivery node (goods from depot
  to customer) or a pure pickup node (goods from customer back to depot). The vehicle
  departs the depot loaded with all of a route's deliveries; the load varies along the
  route and must stay within capacity at **every stop** (position-dependent constraint).
  Time windows in the instance files are ignored; the harness solves the capacity-only
  variant. The objective is lexicographic: minimize number of vehicles first, then total
  distance. No BKS are bundled â€” `gap_pct` is left blank for VRPMPD runs.
- **PVRP** â€” Cordeau benchmark (`data/instances/PVRP/`, `.txt`,
  [source](http://neumann.hec.ca/chairedistributique/data/)): 42 instances split into
  two sets. Old set `old/p01â€“p32` (20â€“417 customers, `t âˆˆ {2,5,6,7,8,10}` periods, no
  route-duration limit). New set `new/pr01â€“pr10` (48â€“288 customers, `t âˆˆ {4,6}` periods,
  per-route duration limit 400â€“500). Each customer has a visit frequency `freq` (1â€“`t`)
  and a list of allowed **combination codes** â€” bitmasks over the `t` days
  (`popcount(code) == freq`) â€” specifying which subsets of days are valid visit patterns.
  A hard per-day fleet cap `m` (1â€“12) limits routes per day; `m=1` instances (p03, p06,
  p09) are the tightest. Euclidean distances are nearest-integer rounded. The objective is
  total travel distance summed across all `t` days (single-stage, no vehicle-count term).
  No BKS are bundled â€” `gap_pct` is left blank for PVRP runs.
- **SDVRP** - DIMACS R1 Split Delivery VRP benchmark (`data/instances/SDVRP_R1_instances/`, `.txt`/`.sd`/`.cri`, [source](http://dimacs.rutgers.edu/index.php/programs/challenge/vrp/vrpsd/)): 95 instances across SET-1 (`SD*.txt`), SET-2 (`S*D*.sd`), SET-3 (`p*_*.cri`), and SET-4 (`eil*.sd`). The format is `n Q`, one demand line with `n` values, then `n+1` coordinate rows with the depot first. Distances use `floor(sqrt(dx^2 + dy^2) + 0.5)`. Official post-challenge BKS values are bundled, so `gap_pct` is reported for SDVRP runs.

`data/bks.csv` (`instance_name, variant, bks_value, rounding, source`) holds curated
best-known values for gap computation. The `rounding` column documents the distance
convention each BKS was computed under (`int` for CVRP, `float`/1-decimal for VRPTW),
kept consistent with the loader. Missing BKS â†’ `gap_pct` is left blank, not an error
(MDVRP, VRPMPD, and PVRP BKS are not bundled; SDVRP R1 BKS values are bundled).

## Correctness model

Every solution is **independently re-scored** against the instance's authoritative
distance matrix and re-checked for feasibility:

- **CVRP / MDVRP** â€” visiting constraints and total route load â‰¤ capacity; MDVRP also
  verifies each route names a valid depot it starts and ends at.
- **VRPTW** â€” visiting constraints, load, and time-window compliance at every stop.
- **VRPMPD** â€” visiting constraints and a position-dependent load walk: the vehicle
  departs each route with load = Î£ deliveries, decrements at delivery stops, increments
  at pickup stops, and the load must remain in `[0, capacity]` after every node.
- **PVRP** â€” each route's assigned day (via `route_days`) is checked; per-customer
  visit-day set must match exactly one allowed combination code; at most `m` routes per
  day; per-route load â‰¤ capacity; (new set) per-route travel + service time â‰¤
  `max_route_duration`. The objective is recomputed as the sum of all route distances
  across all days from the authoritative matrix, so `obj_mismatch â‰ˆ 0` by construction.
- **SDVRP** - `route_deliveries` is required and checked route by route. Delivery keys must match route customers, all delivered quantities must be positive, per-route load must not exceed homogeneous capacity, no depot or invalid node may appear inside a route, and each customer's delivered quantities must sum exactly to its demand. There is no site-dependency, vehicle-type, route-duration, or hard fleet-cap check for R1 SDVRP.

The `obj_mismatch` column flags any disagreement between a solver's reported objective and
the independent recompute (â‰ˆ0 for integer-distance variants; tiny for VRPTW). For VRPMPD
each adapter strips the fixed vehicle cost from its own objective before reporting, so
`obj_mismatch` stays â‰ˆ0 there too.

## Tests

```powershell
.venv\Scripts\python.exe -m pytest -q
```

