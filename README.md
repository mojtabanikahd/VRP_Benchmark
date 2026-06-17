# vrpbench

A fast, reproducible benchmarking harness for **CVRP**, **VRPTW**, **MDVRP**
(multi-depot), and **VRPMPD** (mixed pickup & delivery) that compares complete solvers on
*final solution quality + runtime* only.

Bundled solvers: **PyVRP** (CVRP + VRPTW + MDVRP + VRPMPD), **OR-Tools** (CVRP + VRPTW +
MDVRP + VRPMPD), **VROOM** (CVRP + VRPTW + MDVRP + VRPMPD), and **VRPSolverEasy** (CVRP +
VRPTW — exact BCP via BaPCod; MDVRP and VRPMPD not supported). A future custom solver plugs
in as one adapter file + one registry entry.

## Install

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

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

# Full benchmark — all four solvers on the standard CVRP X-set + Solomon VRPTW set
.venv\Scripts\python.exe -m vrpbench.cli --config experiments/benchmark.yaml
```

Results are appended incrementally to `results/results.csv` (one row per run).

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
```

> **MDVRP files share the `.txt` extension with Solomon VRPTW**, so the variant cannot be
> inferred from the filename — declare `variant: MDVRP` and the loader uses the Cordeau
> parser. `vrpsolvereasy` cannot be listed under an MDVRP or VRPMPD group (config validation
> rejects it with a clear error).
>
> **VRPMPD files use the unique `.vrpmpd` extension** — the variant is inferred automatically
> and no explicit `variant:` declaration is needed (though it is accepted and validated).

## Layout

| Module | Responsibility |
|---|---|
| `vrpbench/core` | `Instance`, `Solution`, independent `evaluate` (objective recompute, feasibility, gap) |
| `vrpbench/datasets` | `loader` (CVRPLIB `.vrp` + Solomon/GH `.txt` via `vrplib`, Cordeau MDVRP `.txt`), curated `bks` table |
| `vrpbench/solvers` | `Solver` protocol + `pyvrp` / `ortools` / `vroom` / `vrpsolvereasy` adapters + `SOLVERS` registry |
| `vrpbench/runner` | YAML `config` + execution loop |
| `vrpbench/results` | incremental CSV store (+ optional per-run JSON) |

## Solvers

| Name | Type | CVRP | VRPTW | MDVRP | VRPMPD | Notes |
|---|---|---|---|---|---|---|
| `pyvrp` | Heuristic (LNS) | ✓ | ✓ | ✓ | ✓ | |
| `ortools` | Heuristic (CP-SAT/LNS) | ✓ | ✓ | ✓ | ✓ | |
| `vroom` | Heuristic (LNS) | ✓ | ✓ | ✓ | ✓ | Windows: numpy `uintc` workaround applied |
| `vrpsolvereasy` | Exact (BCP / BaPCod) | ✓ | ✓ | ✗ | ✗ | Requires BaPCod binaries; ≤ 1022 nodes; needs long time budgets (see below) |

All three heuristic solvers handle multiple depots **natively** (PyVRP per-depot vehicle
types, OR-Tools per-vehicle `starts`/`ends`, VROOM per-vehicle `start`/`end`). MDVRP uses
classic *open* depot assignment — the solver chooses which depot serves each customer.

For **VRPMPD**, PyVRP and VROOM enforce the position-dependent load constraint natively
(each `Client`/`Job` carries both `delivery` and `pickup` amounts). OR-Tools uses a
two-dimension model (`Deliveries` + `Load` dimensions linked per vehicle) to replicate
the same constraint. All three use a large per-vehicle fixed cost to implement the
lexicographic two-stage objective (minimize vehicles first, then distance).

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

`data/bks.csv` (`instance_name, variant, bks_value, rounding, source`) holds curated
best-known values for gap computation. The `rounding` column documents the distance
convention each BKS was computed under (`int` for CVRP, `float`/1-decimal for VRPTW),
kept consistent with the loader. Missing BKS → `gap_pct` is left blank, not an error
(neither MDVRP nor VRPMPD BKS are bundled).

## Correctness model

Every solution is **independently re-scored** against the instance's authoritative
distance matrix and re-checked for feasibility:

- **CVRP / MDVRP** — visiting constraints and total route load ≤ capacity; MDVRP also
  verifies each route names a valid depot it starts and ends at.
- **VRPTW** — visiting constraints, load, and time-window compliance at every stop.
- **VRPMPD** — visiting constraints and a position-dependent load walk: the vehicle
  departs each route with load = Σ deliveries, decrements at delivery stops, increments
  at pickup stops, and the load must remain in `[0, capacity]` after every node.

The `obj_mismatch` column flags any disagreement between a solver's reported objective and
the independent recompute (≈0 for integer-distance variants; tiny for VRPTW). For VRPMPD
each adapter strips the fixed vehicle cost from its own objective before reporting, so
`obj_mismatch` stays ≈0 there too.

## Tests

```powershell
.venv\Scripts\python.exe -m pytest -q
```
