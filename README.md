# vrpbench

A fast, reproducible benchmarking harness for **CVRP**, **VRPTW**, **MDVRP**
(multi-depot), **VRPMPD** (mixed pickup & delivery), **PVRP** (periodic VRP), and
**SDVRP** (site-dependent / split-delivery VRP) that compares complete solvers on *final
solution quality + runtime* only.

Bundled solvers: **PyVRP** (CVRP + VRPTW + MDVRP + VRPMPD), **OR-Tools** (CVRP + VRPTW +
MDVRP + VRPMPD), **VROOM** (CVRP + VRPTW + MDVRP + VRPMPD), **VRPSolverEasy** (CVRP +
VRPTW — exact BCP via BaPCod; MDVRP, VRPMPD, PVRP, and SDVRP not supported), **PVRPSolver**
wrapping any of the three heuristic solvers (`pvrp_pyvrp`, `pvrp_ortools`, `pvrp_vroom`)
for PVRP via ALNS over day-combination assignments, and **SDVRPSolver**, a self-contained
Tabu Search (`sdvrp_tabu`, plus `sdvrp_pyvrp` / `sdvrp_ortools` / `sdvrp_vroom` which seed
the initial solution from a base solver). A future custom solver plugs in as one adapter
file + one registry entry.

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
# Quick smoke test — PyVRP + OR-Tools on one CVRP and one VRPTW instance
.venv\Scripts\python.exe -m vrpbench.cli --config experiments/smoke.yaml

# MDVRP smoke — PyVRP + OR-Tools + VROOM on small Cordeau multi-depot instances
.venv\Scripts\python.exe -m vrpbench.cli --config experiments/mdvrp_smoke.yaml

# VRPMPD smoke — PyVRP + OR-Tools + VROOM on two Salhi-Nagy S instances
.venv\Scripts\python.exe -m vrpbench.cli --config experiments/vrpmpd_smoke.yaml

# PVRP smoke — three PVRP wrappers on one old (no duration limit) + one new (duration limit) instance
.venv\Scripts\python.exe -m vrpbench.cli --config experiments/pvrp_smoke.yaml

# SDVRP smoke — Tabu Search + one base-seeded wrapper on one old + one new site-dependent instance
.venv\Scripts\python.exe -m vrpbench.cli --config experiments/sdvrp_smoke.yaml

# Full benchmark — all four solvers on the standard CVRP X-set + Solomon VRPTW set
.venv\Scripts\python.exe -m vrpbench.cli --config experiments/benchmark.yaml

# Run cells in parallel across 4 worker processes (~4× faster on a 4-core machine)
.venv\Scripts\python.exe -m vrpbench.cli --config experiments/sdvrp_smoke.yaml --threads 4
```

Results are appended incrementally to `results/results.csv` (one row per run). Re-running
the same config **resumes** by default: cells already in the CSV are skipped (see below).

### Running all benchmarks (Linux)

`run_all_benchmarks.sh` runs all five full-benchmark configs sequentially — CVRP/VRPTW,
VRPMPD, SDVRP, PVRP, and MDVRP — in a single invocation. Because every config appends to
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

The script auto-detects the Python interpreter (`.venv/bin/python` → `python3` → `python`),
prints a timestamped header per config, and exits non-zero if any config fails (listing
which ones).

### Resume (skip already-done cells)

Every run reads `results/results.csv` at startup and skips any cell already recorded there,
so an interrupted batch can simply be re-launched to finish the remaining work — no
recomputation of finished cells.

```powershell
# First launch solves the whole grid; if interrupted, just run the same command again —
# it picks up only the cells that have no row yet.
.venv\Scripts\python.exe -m vrpbench.cli --config experiments/benchmark.yaml --threads 8

# Force a full re-run, ignoring existing rows (--no-resume is an alias):
.venv\Scripts\python.exe -m vrpbench.cli --config experiments/benchmark.yaml --force
```

- A cell is identified by `(run_id, instance_name, variant, solver, seed)` — `solver_version`
  and `time_budget_s` are **not** part of the key. Results from a different `run_id` never
  block cells in the current experiment.
- A cell counts as done if it has **any** row (`ok`, `infeasible`, **or `error`**). To retry
  an `error` cell, re-run with `--force` or delete its row from the CSV.
- The startup line reports what was skipped, e.g.
  `Resume: 1430/1600 cells already in results/results.csv; running 170 remaining.`
- `--force` (alias `--no-resume`) **appends** a fresh set of rows; it does not truncate the
  CSV. To start completely clean, point `results_dir` at a new folder or delete the CSV.

### Parallel execution (`--threads N`)

The experiment grid (`instance × solver × seed`) is **embarrassingly parallel**: each cell is
independent. Pass `--threads N` (alias `-j N`) to run up to `N` cells simultaneously across
worker processes, cutting wall-clock time roughly N× on a multi-core machine.

```powershell
.venv\Scripts\python.exe -m vrpbench.cli --config experiments/benchmark.yaml --threads 8
```

- **Default is `--threads 1`** — the original sequential loop, byte-identical to previous behaviour.
- The time budget per cell is **unchanged**: each worker runs on its own core and receives the
  full `time_budget_s`. Keep `N ≤ physical cores` to avoid contention (the CLI warns if you exceed `os.cpu_count()`).
- Result rows land in the CSV in **completion order** (not grid order) when `N > 1`; the set of
  rows is identical to a sequential run.
- A solve exception in one cell is captured as `status=error` and never aborts the batch —
  the same guarantee as the sequential mode.

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
  - variant: SDVRP            # site-dependent / split-delivery VRP; declared explicitly
    instances:
      - data/instances/SDVRP/old/p01.txt
```

> **MDVRP, PVRP, and SDVRP files share the `.txt` extension with Solomon VRPTW**, so their
> variant cannot be inferred from the filename — declare `variant: MDVRP`, `variant: PVRP`,
> or `variant: SDVRP` explicitly and the loader selects the correct Cordeau parser.
> `vrpsolvereasy` cannot be listed under an MDVRP, VRPMPD, PVRP, or SDVRP group (config
> validation rejects it with a clear error). PVRP solvers must use the `pvrp_*` names
> (`pvrp_pyvrp`, `pvrp_ortools`, `pvrp_vroom`) and SDVRP solvers the `sdvrp_*` names
> (`sdvrp_tabu`, `sdvrp_pyvrp`, `sdvrp_ortools`, `sdvrp_vroom`); the plain
> `pyvrp`/`ortools`/`vroom` names do not support PVRP or SDVRP.
>
> **VRPMPD files use the unique `.vrpmpd` extension** — the variant is inferred automatically
> and no explicit `variant:` declaration is needed (though it is accepted and validated).

## Layout

| Module | Responsibility |
|---|---|
| `vrpbench/core` | `Instance`, `Solution`, independent `evaluate` (objective recompute, feasibility, gap) |
| `vrpbench/datasets` | `loader` (CVRPLIB `.vrp` + Solomon/GH `.txt` via `vrplib`, Cordeau MDVRP/PVRP/SDVRP `.txt`, Salhi–Nagy `.vrpmpd`), curated `bks` table |
| `vrpbench/solvers` | `Solver` protocol + `pyvrp` / `ortools` / `vroom` / `vrpsolvereasy` adapters + `pvrp_solver` ALNS wrapper + `sdvrp_solver` Tabu Search + `SOLVERS` registry |
| `vrpbench/runner` | YAML `config` + execution loop (parallel `--threads`, resume / `--force`) |
| `vrpbench/results` | incremental CSV store (+ optional per-run JSON) |

## Solvers

| Name | Type | CVRP | VRPTW | MDVRP | VRPMPD | PVRP | SDVRP | Notes |
|---|---|---|---|---|---|---|---|---|
| `pyvrp` | Heuristic (LNS) | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | |
| `ortools` | Heuristic (CP-SAT/LNS) | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | |
| `vroom` | Heuristic (LNS) | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | Windows: numpy `uintc` workaround applied |
| `vrpsolvereasy` | Exact (BCP / BaPCod) | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | Requires BaPCod binaries; ≤ 1022 nodes; needs long time budgets (see below) |
| `pvrp_pyvrp` | ALNS wrapper (PyVRP inner) | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | |
| `pvrp_ortools` | ALNS wrapper (OR-Tools inner) | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | |
| `pvrp_vroom` | ALNS wrapper (VROOM inner) | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | |
| `sdvrp_tabu` | Tabu Search (greedy init) | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | |
| `sdvrp_pyvrp` | Tabu Search (PyVRP-seeded init) | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | Base solver seeds the initial solution only |
| `sdvrp_ortools` | Tabu Search (OR-Tools-seeded init) | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | Base solver seeds the initial solution only |
| `sdvrp_vroom` | Tabu Search (VROOM-seeded init) | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | Base solver seeds the initial solution only |

All three heuristic solvers handle multiple depots **natively** (PyVRP per-depot vehicle
types, OR-Tools per-vehicle `starts`/`ends`, VROOM per-vehicle `start`/`end`). MDVRP uses
classic *open* depot assignment — the solver chooses which depot serves each customer.

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
solutions are re-evaluated against the authoritative distance matrix so `obj_mismatch ≈ 0`.

For **SDVRP**, none of the base solvers support site-dependency or split delivery, so it is
solved by a self-contained `SDVRPSolver` **Tabu Search**. The fleet is modelled as exactly
`m` route slots per vehicle type (`S = m·t` slots, each with a fixed type), so the per-type
fleet cap is **structural** and never violated. A best-fit construction places customers
into slots — splitting a customer's demand across slots to respect capacity — and the Tabu
Search improves it with Relocate, Swap, and Split-Adjust moves (best-position insertion;
tabu tenure `k = 20` with aspiration). The cost is distance plus a large finite penalty per
unit of infeasibility (capacity / duration overflow + site-incompatible visits), so any
feasible solution strictly beats any infeasible one while the search still has a gradient to
follow; demand coverage is preserved as an invariant. The standalone `sdvrp_tabu` builds its
own greedy initial solution, while `sdvrp_pyvrp` / `sdvrp_ortools` / `sdvrp_vroom` seed the
construction order from a relaxed homogeneous CVRP solved by the base solver (initial
solution only). The wall-clock budget is the primary stop; the no-improvement early-exit
applies only once a feasible solution exists. The reported objective is recomputed as pure
travel distance over the final routes, so `obj_mismatch ≈ 0`. Split delivery is genuine: a
customer may be served by several routes (tracked in `route_deliveries`), which is often
required to fill the tight heterogeneous fleet.

### VRPSolverEasy time budget note

`vrpsolvereasy` is a Branch-Cut-and-Price (BCP) exact solver, not a metaheuristic. Unlike
PyVRP/OR-Tools/VROOM — which always produce a feasible solution quickly and then improve it —
BCP must solve a sequence of LP relaxations before it finds its *first* integer-feasible
solution. On 100+ node instances this can take minutes even with a fast MIP engine.

With the default 10-second flat budget, expect most `vrpsolvereasy` cells to report
`status=infeasible` (no feasible solution found in time), not a suboptimal route set.
This is expected solver behavior, not a bug. For meaningful exact-solver results, set a
much larger budget — e.g., `base_s: 300` or `per_node_ms: 500` — and restrict the instance
set to smaller problems (≤ ~50 nodes) if wall-clock time is a concern.

## Datasets & BKS

Place instance files under `data/instances/`:

- **CVRP** — CVRPLIB X-set (`data/instances/X/`, `.vrp`, EUC_2D, integer-rounded
  distances). 150+ instances with BKS from Uchoa et al. 2017.
- **VRPTW** — Solomon benchmark (`data/instances/Solomon/`, `.txt`, float Euclidean
  distances). Complete 100-customer set (C1/C2/R1/R2/RC1/RC2 classes).
- **MDVRP** — Cordeau benchmark (`data/instances/MDVRP/`, `.txt`,
  [source](http://neumann.hec.ca/chairedistributique/data/)): `old/p01..p21` (integer
  coords) and `new/pr01..pr10` (float coords). Euclidean distances are nearest-integer
  rounded (matching the CVRP convention). The per-depot max-route-duration field is
  ignored (solved as capacity-constrained MDVRP); per-customer PVRP visit-frequency fields
  are discarded.
- **VRPMPD** — Salhi–Nagy "S" benchmark (`data/instances/S/`, `.vrpmpd`,
  [source](http://webhotel4.ruc.dk/~keld/research/LKH-3/)): ~70 instances
  (`CMT01–CMT14` with `H/Q/T/X/Y` variants, 50–199 customers). Euclidean distances are
  nearest-integer rounded. Each customer is either a pure delivery node (goods from depot
  to customer) or a pure pickup node (goods from customer back to depot). The vehicle
  departs the depot loaded with all of a route's deliveries; the load varies along the
  route and must stay within capacity at **every stop** (position-dependent constraint).
  Time windows in the instance files are ignored; the harness solves the capacity-only
  variant. The objective is lexicographic: minimize number of vehicles first, then total
  distance. No BKS are bundled — `gap_pct` is left blank for VRPMPD runs.
- **PVRP** — Cordeau benchmark (`data/instances/PVRP/`, `.txt`,
  [source](http://neumann.hec.ca/chairedistributique/data/)): 42 instances split into
  two sets. Old set `old/p01–p32` (20–417 customers, `t ∈ {2,5,6,7,8,10}` periods, no
  route-duration limit). New set `new/pr01–pr10` (48–288 customers, `t ∈ {4,6}` periods,
  per-route duration limit 400–500). Each customer has a visit frequency `freq` (1–`t`)
  and a list of allowed **combination codes** — bitmasks over the `t` days
  (`popcount(code) == freq`) — specifying which subsets of days are valid visit patterns.
  A hard per-day fleet cap `m` (1–12) limits routes per day; `m=1` instances (p03, p06,
  p09) are the tightest. Euclidean distances are nearest-integer rounded. The objective is
  total travel distance summed across all `t` days (single-stage, no vehicle-count term).
  No BKS are bundled — `gap_pct` is left blank for PVRP runs.
- **SDVRP** — Cordeau type-3 benchmark (`data/instances/SDVRP/`, `.txt`,
  [source](http://neumann.hec.ca/chairedistributique/data/)): 35 instances split into two
  sets. Old set `old/p01–p23` (27–324 customers, `t ∈ {2,3}` vehicle types, no
  route-duration limit, integer service times of 0). New set `new/pr01–pr12` (48–1008
  customers, `t ∈ {4,6}` types, per-route duration limit 500, non-zero service times). Each
  vehicle **type** has its own capacity (60–250) and `m` vehicles are available per type
  (1–21). Each customer carries **combination codes** — MSB-first bitmasks over the `t`
  types — naming the vehicle types allowed to serve it (site-dependency). Euclidean
  distances are nearest-integer rounded. The objective is total travel distance; service
  time counts only toward route-duration feasibility (new set), not the objective. The fleet
  is tight (total demand reaches ~92% of total fleet capacity), so split delivery is often
  required. No BKS are bundled — `gap_pct` is left blank for SDVRP runs.

`data/bks.csv` (`instance_name, variant, bks_value, rounding, source`) holds curated
best-known values for gap computation. The `rounding` column documents the distance
convention each BKS was computed under (`int` for CVRP, `float`/1-decimal for VRPTW),
kept consistent with the loader. Missing BKS → `gap_pct` is left blank, not an error
(MDVRP, VRPMPD, PVRP, and SDVRP BKS are not bundled).

## Correctness model

Every solution is **independently re-scored** against the instance's authoritative
distance matrix and re-checked for feasibility:

- **CVRP / MDVRP** — visiting constraints and total route load ≤ capacity; MDVRP also
  verifies each route names a valid depot it starts and ends at.
- **VRPTW** — visiting constraints, load, and time-window compliance at every stop.
- **VRPMPD** — visiting constraints and a position-dependent load walk: the vehicle
  departs each route with load = Σ deliveries, decrements at delivery stops, increments
  at pickup stops, and the load must remain in `[0, capacity]` after every node.
- **PVRP** — each route's assigned day (via `route_days`) is checked; per-customer
  visit-day set must match exactly one allowed combination code; at most `m` routes per
  day; per-route load ≤ capacity; (new set) per-route travel + service time ≤
  `max_route_duration`. The objective is recomputed as the sum of all route distances
  across all days from the authoritative matrix, so `obj_mismatch ≈ 0` by construction.
- **SDVRP** — each route's vehicle type (via `route_vehicle_types`) and per-customer
  delivered quantities (via `route_deliveries`) are checked: at most `m` routes per type;
  every customer on a route allows that route's type; per-route delivered load ≤ that type's
  capacity; (new set) per-route travel + service time ≤ that type's duration limit; and each
  customer's delivered quantities summed across all routes equal exactly its demand (so
  split delivery is verified end to end). The objective is recomputed as the sum of all route
  distances from the authoritative matrix, so `obj_mismatch ≈ 0` by construction.

The `obj_mismatch` column flags any disagreement between a solver's reported objective and
the independent recompute (≈0 for integer-distance variants; tiny for VRPTW). For VRPMPD
each adapter strips the fixed vehicle cost from its own objective before reporting, so
`obj_mismatch` stays ≈0 there too.

## Tests

```powershell
.venv\Scripts\python.exe -m pytest -q
```
