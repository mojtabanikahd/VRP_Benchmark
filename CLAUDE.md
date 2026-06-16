# Plan: Add the **MDVRP** (Multi-Depot VRP) variant to vrpbench

## Context

The benchmark currently compares four complete VRP solvers — `pyvrp`, `ortools`, `vroom`,
`vrpsolvereasy` — on two variants: **CVRP** and **VRPTW**. We add a third interchangeable
variant, **MDVRP** (Multi-Depot VRP), using the classic Cordeau instances from
`http://neumann.hec.ca/chairedistributique/data/` (format described in `README.TXT`), already
present under `data/instances/MDVRP/old/` (`p01..p21`, integer coords) and
`data/instances/MDVRP/new/` (`pr01..pr10`, float coords).

**Why this scope.** A deeper read of the installed libraries shows that **all four underlying
engines support multi-depot natively** — it is pure configuration, no problem transformation:

| Solver | Native multi-depot mechanism (verified) | In MDVRP scope? |
|---|---|---|
| **PyVRP** 0.11.3 | `ProblemData(depots=[Depot,…])` + one `VehicleType(start_depot=idx, end_depot=idx)` per depot (depot = location index). | ✅ Yes |
| **OR-Tools** | `RoutingIndexManager(n, num_vehicles, starts, ends)` with per-vehicle `starts`/`ends` arrays. | ✅ Yes |
| **VROOM** | per-vehicle `vroom.Vehicle(start=idx, end=idx)`; different vehicles → different depots. | ✅ Yes |
| **VRPSolverEasy** | one `add_vehicle_type(start_point_id=d, end_point_id=d)` per depot — there is an **official `demos/MDVRP.py`** doing exactly this. | ❌ **No — excluded by decision** |

So **MDVRP is covered by PyVRP + OR-Tools + VROOM** (three solvers). VRPSolverEasy, though
natively *capable*, is **excluded** from MDVRP by decision: its free CLP engine may only
support a single vehicle type (multi-depot needs one per depot — see Risks), the CLP/CPLEX
question can't be settled without a costly live solve, and the build cost isn't justified.
Its adapter therefore needs **no change** — it keeps `supported_variants = (CVRP, VRPTW)`,
and `config.py` already raises a clear error if it is mistakenly listed under an MDVRP group.

The architecture is additive: the runner/config/CLI are already driven dynamically off
`VARIANTS` and each solver's `supported_variants`, so adding the variant + a loader +
three per-adapter multi-depot branches is all that's required.

---

## Confirmed decisions

- **Variant name / constant:** `MDVRP`, added to `VARIANTS`.
- **Instances:** both `old/p01..p21` (int coords) **and** `new/pr01..pr10` (float coords).
- **Depot assignment:** classic **open** assignment — any customer may be served by any
  depot; the solver decides. This is the default behavior of every native API above.
- **Route→depot encoding:** add `Solution.route_depots: list[int]` (parallel to `routes`);
  empty for CVRP/VRPTW. Avoids changing the canonical `routes: list[list[int]]` shape.
- **Max route duration `D`:** **ignored** (solved as capacity-constrained MDVRP). The `new`
  instances carry `D=500`; ignoring it consistently across all three MDVRP solvers keeps the
  cross-solver comparison fair. (Documented as a relaxation.)
- **Fleet sizing:** **generous per-depot bound** — ignore the Cordeau `m` (vehicles/depot);
  give each depot `num_customers` vehicles so a feasible solution always exists. Matches the
  existing adapters' `max(1, n-1)` convention; optimum uses far fewer.
- **Per-customer trailing fields** (`1 4 1 2 4 8`, PVRP visit-frequency metadata):
  **silently discarded** — pure MDVRP visits each customer once.
- **VRPSolverEasy:** **excluded** from MDVRP. No adapter change — stays `(CVRP, VRPTW)`.
  Rationale: free-CLP may not support the multiple vehicle types multi-depot requires, the
  CLP/CPLEX question needs a costly live solve to settle, and the payoff doesn't justify it.
- **BKS:** none added for MDVRP for now (evaluator already tolerates missing BKS → gap NaN).

---

## 1. Cordeau MDVRP file format (authoritative — confirmed against `demos/MDVRP.py`)

```
type  m  n  t                 # type=2 (MDVRP, ignore); m=vehicles/depot (ignore);
                              # n=#customers; t=#depots
D_1 Q_1                       # t lines: D=max route duration (IGNORE), Q=capacity
...                           #          (all depots share Q in these instances)
D_t Q_t
id x y svc dem  f a d1 d2 d3 d4   # n customer lines; keep id,x,y,dem; drop svc + 6 PVRP toks
...                               # coords are INT in old/, FLOAT in new/  → parse as float
id x y  0 0 0 0               # t depot lines (at end of file); keep x,y
...
```

- Example `p01.txt` header `2 4 50 4` ⇒ **50 customers, 4 depots**, depot lines `0 80` ⇒
  `D=0, Q=80`. Customers are file-ids `1..50`; depots are file-ids `51..54`.
- `vrplib` does **not** parse this format → we write a small custom parser.
- The bundled demo parser reads coords with `int()` and would crash on `new/pr*` floats — our
  loader must use `float()`.

**Internal node indexing (uniform everywhere): depots first `0..t-1`, customers `t..t+n-1`.**
This matches PyVRP's own location ordering (depots before clients) and generalizes the
existing `depot==0` convention.

---

## 2. Core model changes

### `vrpbench/core/instance.py`
- Add constant `MDVRP = "MDVRP"`; append to `VARIANTS` (currently `(CVRP, VRPTW)` at lines 16–18).
- Add field `depot_indices: tuple[int, ...] | None = None`. Keep `depot: int = 0` (the
  "primary" depot, = `depot_indices[0]`) so single-depot code paths still work.
- Generalize the `customers` property (currently `range(1, num_nodes)`): when
  `depot_indices` is set, return `range(len(depot_indices), num_nodes)` (depots are the
  contiguous `0..t-1` block).
- `__post_init__`: for `variant == MDVRP`, require `depot_indices` non-empty, all `< num_nodes`,
  contiguous from 0, and `depot in depot_indices`.

### `vrpbench/core/solution.py`
- Add `route_depots: list[int] = field(default_factory=list)`. For MDVRP, `route_depots[i]`
  is the depot index of `routes[i]`; empty otherwise. `__post_init__` unchanged
  (`num_vehicles` still derived from non-empty routes).

### `vrpbench/core/evaluate.py`
- `route_distance(instance, route, depot=None)`: default `depot = instance.depot`
  (back-compat); when a depot is passed, anchor the route's first/last legs to it
  (lines 33/34/37 currently hard-code `instance.depot`).
- `total_distance`: for MDVRP, zip `solution.routes` with `solution.route_depots`; otherwise
  use `instance.depot` as today.
- `verify`:
  - "depot appears inside a route" check (line 63) → check membership against **all**
    `depot_indices` for MDVRP.
  - For MDVRP, validate `route_depots` is present, same length as `routes`, and every entry
    is a valid depot index; add a violation otherwise. Compute objective per-route with its
    depot. Customer-visiting (uses the generalized `instance.customers`) and capacity checks
    are unchanged.
  - Time-window check stays VRPTW-only.

---

## 3. Loader / config / runner

### `vrpbench/datasets/loader.py`
- New `_load_cordeau_mdvrp(path) -> Instance`: parse header, `t` depot `D Q` lines (take `Q`,
  ignore `D`), `n` customer lines (keep id/x/y/demand, drop svc + 6 PVRP tokens), `t` depot
  coordinate lines. Build `coords` (depots first), `demands` (0 for depots), Euclidean
  `distance` matrix (float, full `(t+n)²`), `capacity=Q`, `depot_indices=tuple(range(t))`,
  `depot=0`, `num_vehicles=None`. Coords parsed as `float` (handles both old/new).
- `load(path, variant=None)`: when `variant == MDVRP`, dispatch straight to the custom parser
  and return — **before** the extension-based `detect_format` cross-check (which would
  mis-detect the `.txt` file as Solomon/VRPTW). `load()` already accepts `variant`.

### `vrpbench/runner/config.py`
- `VARIANTS` membership check (line ~100) auto-accepts MDVRP once the constant is added.
- Guard the `detect_format` vs declared-variant cross-check (lines ~106–111) so it is skipped
  for `MDVRP` (extension is ambiguous; config's explicit `variant` is authoritative).

### `vrpbench/runner/run.py`
- Pass the dataset group's variant into the loader: `loader.load(path, variant=variant)`
  (currently `loader.load(path)` at line ~67) so MDVRP `.txt` files use the right parser.
  The per-cell `try/except` (lines ~93–94) already isolates any solver failure as
  `status="error"`.

---

## 4. Solver adapters — native multi-depot (three solvers)

Each of the **three** in-scope adapters gains `MDVRP` in `supported_variants` and `_SCALE`
(`MDVRP: 1`, same as CVRP), an MDVRP branch in its model-build, and **must populate
`route_depots`** in the returned `Solution`. Common pattern: depots =
`instance.depot_indices`, customers = `instance.customers`,
`vehicles_per_depot = num_customers`. **`vrpsolvereasy_solver.py` is untouched.**

- **`pyvrp_solver.py`** — `depots=[pyvrp.Depot(coords[d]) for d in depot_indices]`; one
  `pyvrp.VehicleType(num_available=num_customers, capacity=[Q], start_depot=d, end_depot=d, …)`
  per depot; clients at indices `t..t+n-1`; full distance/duration matrices. Route extraction:
  `r.visits()` → customer indices, `r.start_depot()` → `route_depots` entry. (PyVRP 0.11.3
  `VehicleType(start_depot, end_depot)` take location indices — verified.)
- **`ortools_solver.py`** — `num_vehicles = t * vehicles_per_depot`; build `starts`/`ends`
  arrays assigning vehicles round-robin to depots; `RoutingIndexManager(n, num_vehicles, starts, ends)`
  (replaces the single-`depot` form at line 45). Capacity dimension unchanged. Route
  extraction (`_extract_routes`, lines ~140–151): record each vehicle's start depot →
  `route_depots`.
- **`vroom_solver.py`** — create `t * vehicles_per_depot` vehicles, each
  `vroom.Vehicle(start=d, end=d, capacity=[Q])` with `d` its assigned depot (lines ~186–195).
  Route extraction (`_to_solution`, lines ~92–114): map `vehicle_id` → its depot →
  `route_depots`.
- **`vrpsolvereasy_solver.py`** — **no change.** Stays `(CVRP, VRPTW)`; excluded from MDVRP.

---

## 5. Tests & smoke config

- **`tests/data/toy_mdvrp.txt`** — tiny Cordeau-format instance (2 depots, ~4 customers) for
  fast solver tests.
- **`tests/test_mdvrp_loader.py`** — parse `toy_mdvrp.txt` and a real `old/p01.txt`: assert
  `variant==MDVRP`, depot count/`depot_indices`, customer count, demands, capacity from `Q`,
  float coords, symmetric distance. Add a `new/pr01.txt` case to lock float parsing.
- **Extend `test_pyvrp_solver.py`, `test_ortools_solver.py`, `test_vroom_solver.py`** — one
  MDVRP case each: `evaluate.verify` feasible, `objective > 0`, `obj_mismatch ≈ 0`,
  `route_depots` populated and all-valid. (`test_vrpsolvereasy_solver.py` is untouched.)
- **`tests/test_core.py`** (or evaluate test) — MDVRP `route_distance` anchors to the correct
  per-route depot.
- **`experiments/mdvrp_smoke.yaml`** — the **three** MDVRP solvers (`pyvrp`, `ortools`,
  `vroom`) on the toy + one small instance, tiny budget; confirm `results.csv` rows with
  `status=ok`, valid `route_depots`, `obj_mismatch ≈ 0`.

---

## 6. Implementation roadmap (dependency order)

1. **Core model:** `instance.py` (MDVRP const, `depot_indices`, `customers` property,
   validation) + `solution.py` (`route_depots`).
2. **Loader/config/runner:** `_load_cordeau_mdvrp` + `load()` dispatch; `config.py` detect
   guard; `run.py` pass `variant`. *Test:* `loader.load("…/old/p01.txt", variant="MDVRP")`
   yields 50 customers / 4 depots.
3. **Evaluator:** depot-parameterized `route_distance`, MDVRP branch in `total_distance` /
   `verify`.
4. **Adapters (three):** add MDVRP branch + `route_depots`. Order by friction:
   OR-Tools and VROOM (low) → PyVRP (medium). *Test:* ad-hoc solve of `toy_mdvrp.txt` per
   solver → feasible, `obj_mismatch ≈ 0`. (`vrpsolvereasy` untouched.)
5. **Tests + toy instance + smoke YAML.** *Test:* `pytest -q` green.
6. **End-to-end smoke:** `python -m vrpbench.cli --config experiments/mdvrp_smoke.yaml` →
   MDVRP rows for the three solvers, `status=ok`, valid `route_depots`.

---

## 7. Risks

- **VRPSolverEasy excluded (decision, not a bug):** `src/solver.py` docstring
  (lines 1269–1270) states *"For academic version, with CLP it's possible to resolve the
  problem with only one vehicle type"* — but multi-depot needs **one vehicle type per
  depot**. `demos/MDVRP.py` defaults to `solver_name="CLP"`, so it is genuinely unclear
  whether free-CLP handles MDVRP or whether CPLEX is required, and resolving it needs a costly
  live solve. We therefore **leave VRPSolverEasy at `(CVRP, VRPTW)`** and cover MDVRP with the
  other three. If exact MDVRP results are wanted later, revisit with CPLEX.
- **Float coords (new instances):** the bundled demo parser uses `int()` and crashes on
  `pr*`; our loader parses `float` to handle both sets.
- **`route_depots` correctness:** every adapter must correctly map each route to its depot;
  the evaluator independently validates membership and re-scores the objective per depot.
- **Node-indexing consistency:** depots `0..t-1`, customers after — must be identical across
  loader, evaluator, and the three MDVRP adapters, or objectives/feasibility diverge.
- **Ignoring `D`:** `new` instances become a capacity-only relaxation; acceptable because it
  is applied uniformly to all solvers and BKS comparison is out of scope here. Documented.
- **Distance convention:** all solvers read `instance.distance` and apply the same
  `_SCALE`+`np.rint`, so costs are byte-identical; the evaluator re-scores everyone.

---

## Verification (end-to-end)

1. `loader.load(".../MDVRP/old/p01.txt", variant="MDVRP")` → 50 customers, 4 depots,
   `depot_indices == (0,1,2,3)`, capacity 80; `new/pr01.txt` parses floats without error.
2. `pytest tests/test_mdvrp_loader.py tests/test_*_solver.py -q` → loader correct; each solver
   produces a feasible MDVRP solution with valid `route_depots` and `obj_mismatch ≈ 0`.
3. `pytest -q` → full suite still green (CVRP/VRPTW unaffected; runner/config pick up MDVRP
   dynamically).
4. `python -m vrpbench.cli --config experiments/mdvrp_smoke.yaml` → MDVRP rows for
   `pyvrp`, `ortools`, `vroom`; `status=ok`, valid `route_depots`, `obj_mismatch ≈ 0`.
