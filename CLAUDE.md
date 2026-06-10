# Plan: Add a `pyvroom` (VROOM) solver backend to vrpbench

## Context

The benchmark compares *complete* VRP solvers on CVRP and VRPTW. Two adapters
exist today — [`PyVRPSolver`](vrpbench/solvers/pyvrp_solver.py) and
[`OrToolsSolver`](vrpbench/solvers/ortools_solver.py) — both satisfying the
`Solver` protocol in [base.py](vrpbench/solvers/base.py). We want to add VROOM
(via the `pyvroom` package, imported as `vroom`) as a third interchangeable
solver so research comparisons include a fast, heuristic, open-source engine.

The architecture is already designed for exactly this: adapters are self-contained,
registered by name in one dict ([solvers/__init__.py](vrpbench/solvers/__init__.py)),
and every consumer (runner, config validation, CLI) is driven dynamically off
`SOLVERS` and each solver's `supported_variants`. **No abstraction layer, data
model, or unrelated module needs to change.** The work is: one new adapter file,
one registry entry, one requirements line, one test file.

**Confirmed decisions:**
- **Time budget:** pyvroom 1.15.2's `solve()` signature is
  `solve(exploration_level, nb_threads=4, timeout: timedelta|None=None, depth=None)`
  — it *does* accept a wall-clock `timeout`. The adapter **honors `time_budget_s`**
  via `timeout=timedelta(seconds=time_budget_s)`, with a high `exploration_level`
  (default **5**) and `nb_threads=1` (determinism). This keeps vroom comparable to
  OR-Tools/PyVRP under the same shared budget. `seed` is accepted but ignored
  (VROOM is deterministic at `nb_threads=1`), mirroring `OrToolsSolver`.
- **Registry name:** `vroom`.
- **Windows compatibility (RESOLVED):** `set_durations_matrix` raises
  `Incompatible buffer format!` on Windows because pyvroom hard-casts to numpy
  `uint32` (format `'L'` on MSVC) while `_vroom.Matrix` expects `'I'`. The adapter
  bypasses this by building `_vroom.Matrix(np.ascontiguousarray(M, dtype=np.uintc))`
  itself and passing that object. Verified end-to-end on Python 3.12.8 / pyvroom
  1.15.2. Full root-cause + upstream issue #85 in
  [PYVROOM_COMPATIBILITY_ISSUE.md](PYVROOM_COMPATIBILITY_ISSUE.md).

---

## 1. Feasibility Assessment

VROOM is a complete heuristic VRP solver and natively models both target variants.

### CVRP
- **Supported:** single depot; per-vehicle capacity (`capacity=[c]`); per-customer
  demand as a delivery amount (`delivery=[d]`); a custom integer cost/duration
  matrix as the routing objective; arbitrary fleet size; objective =
  minimize total travel cost (we feed the distance matrix as that cost).
- **Unsupported / not needed:** multiple depots, heterogeneous capacities,
  pickups, skills, priorities — none used by our `Instance`.
- **Assumptions/limitations:** VROOM optimises over **integers** (matrix, amounts).
  We reuse the existing per-variant scale (`CVRP -> 1`, the matrix is already
  integer-valued in CVRPLIB). If the chosen fleet is too small VROOM does *not*
  error — it returns a solution with some jobs **unassigned**, which we must
  detect and treat as infeasible.

### VRPTW
- **Supported:** customer time windows (`time_windows=[[e, l]]`), service
  durations (`service=s`), vehicle/depot time window (`time_window=[e, l]`).
  VROOM uses the **duration matrix** both as the cost objective *and* for arrival-
  time computation. Because Solomon/GH travel time == distance, a single scaled
  matrix correctly serves both roles — exactly the assumption the PyVRP and
  OR-Tools adapters already make.
- **Unsupported / not needed:** multiple time windows per customer (we have one),
  driver breaks, max route duration/distance limits — none used.
- **Assumptions/limitations:** integer times -> reuse scale `VRPTW -> 10` (DIMACS
  convention, matching PyVRP, OR-Tools, and the 1-decimal Solomon/GH BKS).
  Waiting before a window opens is allowed by VROOM (consistent with our
  evaluator's `_check_time_windows`). VROOM minimises total **duration** (= our
  scaled distance), so its objective aligns with the benchmark's distance gap.

**Conclusion:** both variants are fully supported with the same scaling and
matrix conventions already in the codebase. The only genuine mismatch is the
time-budget knob (handled by the confirmed fixed-exploration policy).

---

## 2. Architecture Impact

Minimum changes — additive only.

**New module (1 file):**
- [vrpbench/solvers/vroom_solver.py](vrpbench/solvers/vroom_solver.py) — the
  `VroomSolver` adapter implementing the `Solver` protocol.

**Modified modules (2 files, one line each):**
- [vrpbench/solvers/__init__.py](vrpbench/solvers/__init__.py) — add a
  `_make_vroom()` lazy factory and a `"vroom"` entry in `SOLVERS`.
- [requirements.txt](requirements.txt) — add `pyvroom` (and `pandas`, see §4 note).

**New test (1 file):**
- `tests/test_vroom_solver.py` — mirrors
  [tests/test_pyvrp_solver.py](tests/test_pyvrp_solver.py).

**Explicitly NOT changed (interfaces are sufficient):**
- `Solver` protocol — unchanged; `VroomSolver` satisfies it as-is.
- `Instance` / `Solution` — reused verbatim; no new fields, no new data model.
- [runner/run.py](vrpbench/runner/run.py) — already iterates `cfg.solvers` and
  calls `get_solver`; picks up `vroom` for free.
- [runner/config.py](vrpbench/runner/config.py) — validation reads `SOLVERS` and
  `supported_variants` dynamically; the new solver is accepted with no edit.
- [cli.py](vrpbench/cli.py), [core/evaluate.py](vrpbench/core/evaluate.py),
  [results/store.py](vrpbench/results/store.py),
  [datasets/loader.py](vrpbench/datasets/loader.py) — untouched.

---

## 3. Data Mapping (`Instance` -> VROOM)

VROOM is matrix-indexed: when a custom matrix is supplied, vehicles reference
matrix rows via `start`/`end` indices and jobs via a `location` index. We keep
the mapping trivial by setting each job's `id` **and** `location` to its node
index, so solution job-ids come back as our customer indices directly.

| `Instance` field | VROOM concept | Conversion |
|---|---|---|
| `depot` (default 0) | `Vehicle.start` / `Vehicle.end` | pass the depot node index (VROOM supports any index; no depot==0 restriction needed) |
| customers `1..n-1` | `Job` per customer | `vroom.Job(id=i, location=i, ...)` |
| `coords` | — | **not used** (custom matrix supersedes coordinates) |
| `distance` (n×n, authoritative) | duration matrix (the cost objective) | `np.rint(distance * scale).astype(np.int64)` -> wrap as `_vroom.Matrix(np.ascontiguousarray(M, dtype=np.uintc))` (Windows-safe, see §Context) -> `input.set_durations_matrix(profile, that_matrix)` |
| travel times (VRPTW) | same duration matrix | travel time == distance (Solomon/GH); the one matrix serves cost + time |
| `capacity` | `Vehicle.capacity` | `[int(capacity)]` (1-D amount vector) |
| `demands[i]` | `Job.delivery` | `[int(demands[i])]` (goods loaded at depot, delivered to customer) |
| `time_windows[i]` (VRPTW) | `Job.time_windows` | `[[int(e*scale), int(l*scale)]]` |
| depot `time_windows` (VRPTW) | `Vehicle.time_window` | `[int(e*scale), int(l*scale)]` |
| `service_times[i]` (VRPTW) | `Job.service` | `int(s*scale)` |
| fleet size | N `Vehicle` objects | see §4 fleet sizing |

**Profile:** use one profile name (VROOM default `"car"`) consistently for the
matrix and all vehicles. **Amount dimension:** all `capacity` and `delivery`
vectors are length 1 and must agree (they do). **Scale:** reuse the module-level
`_SCALE = {CVRP: 1, VRPTW: 10}` constant, identical to the other two adapters.

---

## 4. Solver Wrapper Design — `solvers/vroom_solver.py`

**Responsibilities**
- Translate one `Instance` into a `vroom.Input`.
- Run VROOM with the fixed-exploration policy.
- Translate the VROOM solution back into our `Solution`.
- Report the engine version for reproducibility.

**Public API (the `Solver` protocol — nothing more):**
```
class VroomSolver:
    name = "vroom"
    supported_variants = (CVRP, VRPTW)
    def __init__(self, exploration_level: int = 5, nb_threads: int = 1): ...
    def solve(self, instance, *, time_budget_s, seed) -> Solution
    def version(self) -> str
```
Engine knobs (`exploration_level`, `nb_threads`) live as **constructor defaults**,
exactly as the base-class docstring prescribes — they never leak into `solve()`'s
signature, preserving interchangeability.

**Internal workflow of `solve()`**
1. Deferred `import vroom` (and `pandas` only if needed) inside `solve()`, matching
   the lazy-import pattern of the other adapters (a missing optional dep must not
   break unrelated solvers).
2. Guard `instance.variant in _SCALE` else raise `SolverError`.
3. Build the scaled integer matrix from `instance.distance`, then wrap it as a
   `_vroom.Matrix` via the Windows-safe `np.uintc` helper (see §Context).
4. Construct `vroom.Input()`; `set_durations_matrix(profile, vroom_matrix)`.
5. Add jobs (one per customer): CVRP -> `delivery=[demand]` only; VRPTW -> also
   `service` + `time_windows=[[e, l]]`.
6. Add the fleet (see sizing below): each `Vehicle(id, start=depot, end=depot,
   capacity=[cap])`, plus `time_window=[depot_e, depot_l]` for VRPTW.
7. `start = perf_counter()`; `solution = input.solve(
   exploration_level=self.exploration_level, nb_threads=self.nb_threads,
   timeout=timedelta(seconds=time_budget_s))`;
   `runtime_s = perf_counter() - start`. **`seed` is ignored** for search control
   (VROOM is deterministic at `nb_threads=1`).
8. Convert to `Solution` (see §5).

**Fleet sizing.** Add `max(1, n - 1)` vehicles — one per customer, the same safe
feasibility upper bound PyVRP uses. VROOM only routes vehicles it needs; surplus
vehicles stay empty (dropped in extraction). Over-provisioning avoids spurious
unassigned jobs. (Optionally reuse OR-Tools' `_vehicle_count` lower bound, but
`n-1` is simpler and strictly safe; recommend `n-1`.)

**Interaction with pyvroom.** Use the in-process matrix API only (`vroom.Input`,
`set_durations_matrix`, `add_job`, `add_vehicle`, `Input.solve`). No routing
server, no OSRM, no file I/O. `pyvroom` pulls in `pandas` (its solution is a
DataFrame) — pin it in requirements to be explicit.

> **API confirmed against the installed pyvroom 1.15.2 (Python 3.12.8, Windows).**
> - Demand kwarg is `delivery=[...]` on `vroom.Job`.
> - `vroom.Job(id=, location=, delivery=, service=, time_windows=[[e, l]])`.
> - `vroom.Vehicle(id=, start=, end=, capacity=[...], time_window=[e, l])`.
> - `Input.solve(exploration_level, nb_threads=4, timeout: timedelta|None=None,
>   depth=None)`.
> - Matrix must be wrapped as `_vroom.Matrix(np.ascontiguousarray(M, dtype=np.uintc))`
>   on Windows (see §Context / PYVROOM_COMPATIBILITY_ISSUE.md).

---

## 5. Solution Conversion (VROOM result -> `Solution`)

VROOM returns a solution whose `routes` is a `pandas.DataFrame` (confirmed columns:
`['vehicle_id', 'type', 'arrival', 'duration', 'setup', 'service', 'waiting_time',
'location_index', 'id', 'description']`), one row per step (`type` in
{`start`,`job`,`end`,...}), plus a `summary` with aggregate `cost`/`unassigned`.

- **routes:** group rows by `vehicle_id`, keep `type == "job"` rows in order,
  collect their `id` (== our customer index) into a list, **casting each to `int`**
  (they come back as `np.int64`); drop empty lists. Produces `list[list[int]]` of
  customer indices with the depot implied — exactly our canonical `Solution.routes`
  form.
- **objective:** `summary.cost / scale`. Since the cost matrix == scaled distance,
  this is VROOM's own distance claim. It is only a cross-check — the evaluation
  layer always re-scores against `instance.distance` (`obj_mismatch` reported).
- **vehicle count:** leave `num_vehicles=0`; `Solution.__post_init__` derives it
  as the count of non-empty routes.
- **feasibility:** `feasible = (number of unassigned jobs == 0)` from
  `summary.unassigned` (or `len(solution.unassigned)`). The evaluator independently
  re-verifies (unvisited customers, capacity, time windows) and has final say on
  the run's `status`.
- **runtime:** wall-clock `perf_counter` delta around `input.solve()`, consistent
  with the other adapters (not VROOM's internal `computing_times`).

---

## 6. Error Handling

| Failure | Detection | Handling |
|---|---|---|
| Unsupported variant | `variant not in _SCALE` | raise `SolverError` (parity with PyVRP/OR-Tools) |
| Invalid input data (bad shapes) | already enforced by `Instance.__post_init__` | nothing extra; trust the validated `Instance` |
| `pyvroom` not installed | deferred `import vroom` raises `ModuleNotFoundError` | propagates; runner records that single cell as `status="error"` and continues (no global break) |
| VROOM runtime error (bad matrix/amount dims) | exception from `input.solve()` / `add_*` | wrap in `SolverError` with context |
| Infeasible (jobs unassigned) | `summary.unassigned > 0` | return `Solution(feasible=False, ...)`; evaluator marks `status="infeasible"` (the route is still recorded) |

The runner's per-cell `try/except` ([run.py](vrpbench/runner/run.py) `_run_cell`)
already guarantees one bad cell never aborts the batch, so the adapter only needs
to raise clear errors and never swallow them silently.

---

## 7. Validation Strategy

New file `tests/test_vroom_solver.py`, mirroring
[tests/test_pyvrp_solver.py](tests/test_pyvrp_solver.py), using the bundled
fixtures [tests/data/toy.vrp](tests/data/toy.vrp) (CVRP) and
[tests/data/toy_solomon.txt](tests/data/toy_solomon.txt) (VRPTW).

**Small CVRP (`toy.vrp`)**
- Expected: `evaluate.verify(...)` returns `feasible=True`; `objective ≈ 8.0`
  (the independently known toy optimum, already asserted for PyVRP);
  `obj_mismatch ≈ 0` (integer CVRP, scale 1); `runtime_s > 0`.

**Small VRPTW (`toy_solomon.txt`)**
- Expected: `feasible=True`; `objective > 0`. (Exact value not pinned, matching
  the PyVRP test.)

**Consistency checks**
- Determinism: solving twice yields identical `routes` (guaranteed by
  `nb_threads=1`, deterministic VROOM, no seed dependence).
- `version()` returns a real version (not `"unknown"`).
- Every customer visited exactly once, capacity respected, TW respected — all
  enforced by `evaluate.verify` (asserted via `ev.feasible`).

**Cross-solver comparison (manual / smoke).** Add `vroom` to a scratch experiment
(or temporarily to [experiments/smoke.yaml](experiments/smoke.yaml)) alongside
`pyvrp` and `ortools`. On the same instances all three must:
- be `feasible`/`status=ok`;
- visit all customers exactly once (already verified);
- produce objectives in the same ballpark (VROOM, being heuristic, may differ but
  should be within a few % on small instances). Large divergence signals a
  scaling/matrix/mapping bug.
- VROOM's `obj_mismatch` should be ~0 after descaling (sanity-checks the
  cost-matrix == distance assumption).

---

## 8. Implementation Roadmap

Each step is independently testable and < 1 hour.

**Step 1 — DONE (API & Windows workaround confirmed).** pyvroom 1.15.2 is installed
in the Windows Python 3.12.8; the API names, `solve` timeout, solution columns, and
the `np.uintc` matrix workaround are all verified end-to-end (toy CVRP solves to
optimum 8). See [PYVROOM_COMPATIBILITY_ISSUE.md](PYVROOM_COMPATIBILITY_ISSUE.md).

**Step 2 — Add dependency.** Add `pyvroom>=...` (and `pandas>=...`) to
[requirements.txt](requirements.txt). *Files:* `requirements.txt`. *Test:*
`pip install -r requirements.txt` clean; `python -c "import vroom"`.

**Step 3 — Skeleton adapter.** Create
[vrpbench/solvers/vroom_solver.py](vrpbench/solvers/vroom_solver.py) with the
class, `name`, `supported_variants`, `_SCALE`, constructor defaults, `version()`,
and a `solve()` that raises `NotImplementedError`. *Files:* new adapter. *Test:*
`from ... import VroomSolver; isinstance(VroomSolver(), Solver)` (runtime-checkable
Protocol) is `True`; `version()` != `"unknown"`.

**Step 4 — Input builder.** Implement matrix scaling, jobs, and fleet for **CVRP**
first (`_build_input`). *Files:* adapter. *Test:* build input from `toy.vrp` with
no exception; inspect job/vehicle counts.

**Step 5 — Solve + convert (CVRP).** Wire `input.solve(...)`, route extraction,
objective descaling, feasibility, runtime. *Files:* adapter. *Test:* the CVRP case
of `tests/test_vroom_solver.py` (`objective ≈ 8.0`, feasible, `obj_mismatch ≈ 0`).

**Step 6 — VRPTW support.** Extend `_build_input` with `service`, job
`time_windows`, vehicle `time_window`, scale 10. *Files:* adapter. *Test:* the
VRPTW case (feasible, `objective > 0`).

**Step 7 — Register the solver.** Add `_make_vroom()` + `"vroom"` to
[vrpbench/solvers/__init__.py](vrpbench/solvers/__init__.py). *Files:* registry.
*Test:* `get_solver("vroom")` returns the adapter; `load_config` accepts a config
listing `vroom` for both variants (no edit to config.py needed).

**Step 8 — Full test file + determinism.** Complete `tests/test_vroom_solver.py`
(CVRP, VRPTW, determinism, version). *Files:* test. *Test:* `pytest
tests/test_vroom_solver.py` green; full suite still green.

**Step 9 — End-to-end smoke.** Run a scratch experiment YAML with all three
solvers via `python -m vrpbench.cli --config ...`; confirm `vroom` rows appear in
`results.csv` with `status=ok` and comparable objectives. *Files:* a scratch
config (optional). *Test:* CSV inspection / cross-solver sanity.

---

## 9. Risk Assessment

**Correctness risks**
- *pyvroom API drift* (`delivery` vs `amount`, solve signature, DataFrame columns).
  → Step 1 pins the real API before coding; deferred import keeps blast radius to
  the vroom cell only.
- *Cost vs duration confusion in VRPTW.* VROOM uses the duration matrix as both
  cost and time. → We deliberately feed one matrix (= scaled distance) and assert
  `obj_mismatch ≈ 0` against the independent evaluator to catch any mismatch.
- *Silent unassigned jobs* read as a "solution." → Explicitly check
  `summary.unassigned`; the evaluator's unvisited-customer check is a second net.

**Reproducibility risks**
- *No seed; thread non-determinism.* → Force `nb_threads=1` and fixed
  `exploration_level`; assert run-to-run identical routes in tests. Record
  `version()` (already persisted by the runner) so engine changes are traceable.

**Windows binding risk (RESOLVED)**
- *`Incompatible buffer format!`* on `set_durations_matrix` (pyvroom #85, open
  upstream, no released fix). → Resolved locally by building `_vroom.Matrix` from a
  `np.uintc` array and passing the object (skips pyvroom's bad `uint32` cast).
  Centralize this in one helper; if a future pyvroom release fixes #85 the helper
  still works. Verified on this machine.

**Benchmark-consistency risks**
- *Time budget* — vroom now **honors** `time_budget_s` via `timeout=timedelta(...)`,
  so it competes under the same wall-clock budget as OR-Tools/PyVRP. Risk reduced
  to: VROOM may converge before the budget (it is fast) and stop early; the
  recorded `runtime_s` makes this auditable, and `exploration_level` remains a
  fixed, reproducible knob.
- *Scaling divergence from the other adapters.* → Reuse the identical
  `_SCALE = {CVRP: 1, VRPTW: 10}` constant and `np.rint(... ).astype(int)` rounding,
  so all three solvers see byte-identical integer matrices; the evaluator re-scores
  everyone against the same authoritative `instance.distance`.

---

## Verification (end-to-end)

1. `pip install -r requirements.txt` — pyvroom imports.
2. `pytest tests/test_vroom_solver.py -q` — CVRP `objective ≈ 8.0`, VRPTW feasible,
   determinism, version all pass.
3. `pytest -q` — full suite still green (proves no regression; config/runner pick
   up `vroom` with zero edits).
4. `python -m vrpbench.cli --config <scratch-with-all-3-solvers>.yaml` — `results.csv`
   shows `vroom` rows, `status=ok`, objectives within a few % of `pyvrp`/`ortools`,
   `obj_mismatch ≈ 0`.
