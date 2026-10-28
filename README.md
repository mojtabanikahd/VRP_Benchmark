# vrpbench

**English** · [فارسی](README.fa.md)

A reproducible benchmarking harness for the vehicle routing problem. It runs complete solvers on the same instances, under the same time budget, and scores every solution itself. The comparison is final solution quality and runtime.

The harness covers six variants:

| Variant | Problem |
| --- | --- |
| **CVRP** | Capacitated VRP. One depot, one visit per customer, route load at most the vehicle capacity. |
| **VRPTW** | VRP with time windows. Service at each customer must start and finish inside that customer's window. |
| **MDVRP** | Multi-depot VRP. Any customer may be served from any depot; the solver chooses. |
| **VRPMPD** | Mixed pickup and delivery. Each customer is either a delivery or a pickup, and the load must stay inside capacity after every stop. |
| **PVRP** | Periodic VRP. Each customer is visited on an allowed subset of days, and each day is routed separately. |
| **SDVRP** | Split-delivery VRP on the DIMACS R1 corpus. A customer may be served by more than one route, and the delivered quantities must sum to the demand. |

An interactive front end for building and solving a scenario lives in [VRP Route Studio](web/README.md) ([فارسی](web/README.fa.md)).

## Contents

- [How the system works](#how-the-system-works)
- [Requirements](#requirements)
- [Installation](#installation)
- [Run a benchmark](#run-a-benchmark)
- [Results, resume, and parallel runs](#results-resume-and-parallel-runs)
- [Reports](#reports)
- [Experiment configuration](#experiment-configuration)
- [Solvers](#solvers)
- [Datasets and best-known solutions](#datasets-and-best-known-solutions)
- [How solutions are checked](#how-solutions-are-checked)
- [Repository layout](#repository-layout)
- [Tests](#tests)

## How the system works

An experiment is a YAML file. It names the solvers, the random seeds, the time budget, and the instance files. The runner expands that file into a grid of cells. One cell is one instance, one solver, and one seed.

```text
experiment YAML
    -> runner (one cell = instance x solver x seed)
        -> loader        builds an Instance from the file
        -> solver        returns a Solution within the time budget
        -> evaluator     recomputes distance and checks feasibility
        -> result store  appends one row to results/results.csv
```

Five packages do this work:

| Package | Role |
| --- | --- |
| `vrpbench/core` | The shared `Instance` and `Solution` types, and the independent evaluator. |
| `vrpbench/datasets` | Parsers for each instance format, and the best-known-solution table. |
| `vrpbench/solvers` | One adapter per solver, plus the registry a new solver plugs into. |
| `vrpbench/runner` | YAML loading, the cell grid, resume, and parallel workers. |
| `vrpbench/results` | Incremental CSV output, and an optional JSON dump of routes. |

The evaluator is the authority for the recorded objective. Each adapter may report its own cost, and `obj_mismatch` is the difference between that report and the recomputed distance. A correct adapter stays near zero.

A new solver is one adapter that follows the `Solver` protocol, plus one entry in `vrpbench/solvers/__init__.py`. The runner, the CSV schema, and the evaluator stay as they are.

`pyproject.toml` is the dependency list. `requirements.txt` contains a single line, `-e .[dev]`, which installs this repository in editable mode together with the development extra (pytest).

## Requirements

| Requirement | Version | Used for |
| --- | --- | --- |
| Python | 3.11 or newer | The harness, every bundled solver, and the web API. |
| pip | Current (the installer upgrades it) | Package installation. |
| Git | Any current release | Cloning the repository. |
| Node.js | 20 or newer | The web studio only. See [web/README.md](web/README.md). |

The PyPI packages `pyvrp`, `ortools`, `pyvroom`, and `VRPSolverEasy` publish wheels for Windows, Linux, and macOS, so a C++ compiler is not required for the default install.

Two solvers need something the wheels do not ship:

- **VRPSolverEasy** needs the BaPCod shared library. CVRP and VRPTW runs that list `vrpsolvereasy` fail until [that library is copied in](#optional-vrpsolvereasy-and-bapcod).
- **Alkaid-SDVRP** is an external executable. SDVRP runs that list `alkaid_sdvrp` need it on the machine and `ALKAID_SDVRP_EXECUTABLE` set in the same shell. See [ALKAID_SETUP.md](ALKAID_SETUP.md).

PyVRP, OR-Tools, and VROOM need no extra binaries.

## Installation

Run every command from the repository root, the directory that contains `pyproject.toml`.

Check the interpreter first:

```bash
python3 --version
```

On Windows, if `python3` is not on `PATH`:

```powershell
py -3 --version
```

The reported version must be 3.11 or newer. If the system Python is older, install a current one and create the virtual environment with that interpreter. The sections below name a concrete installer for each operating system.

### Windows

1. Install Python 3.11 or newer from [python.org](https://www.python.org/downloads/windows/). In the installer, enable **Add python.exe to PATH**. A current Python from `winget install Python.Python.3.12` is the same requirement.
2. Open **PowerShell** in the repository root.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Calling `.venv\Scripts\python.exe` does not require activating the environment, which avoids PowerShell execution-policy prompts. To put `python` and `vrpbench` on the path of the current window:

```powershell
.\.venv\Scripts\Activate.ps1
```

If Windows refuses to run that script, allow local scripts for the current user and try again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Command Prompt uses `.venv\Scripts\activate.bat` instead of `Activate.ps1`.

`run_all_benchmarks.sh` is a Bash script. Run it from [Git Bash](https://git-scm.com/download/win) or from WSL, or run the five full configs yourself in PowerShell (listed under [Run a benchmark](#run-a-benchmark)).

### Linux

Debian, Ubuntu, and their derivatives need the venv module as its own package:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Fedora, RHEL, and related distributions:

```bash
sudo dnf install -y python3 python3-pip git
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

`source .venv/bin/activate` lasts for that terminal. A new terminal needs it again. Without activation, call `.venv/bin/python` directly.

### macOS

Install the Xcode command-line tools once (Git, and a compiler if a wheel ever has to be built locally):

```bash
xcode-select --install
```

Install Python 3.11 or newer with [Homebrew](https://brew.sh/):

```bash
brew install python@3.12
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The python.org macOS installer works as well. Create the virtual environment with that `python3`, not with the older `/usr/bin/python3` shipped by some macOS releases.

Apple silicon and Intel need their own wheels. Create the virtual environment on the machine that will run the benchmarks so pip selects the matching builds. The same rule applies to the BaPCod binaries below: download the macOS archive that matches the machine.

`run_all_benchmarks.sh` uses `nproc` when it is present. macOS does not provide `nproc`, so the script falls back to one worker unless you pass a count:

```bash
chmod +x run_all_benchmarks.sh
./run_all_benchmarks.sh --threads "$(sysctl -n hw.ncpu)"
```

### Confirm the install

With the virtual environment active (or by calling its interpreter directly):

```bash
python -c "import vrpbench, pyvrp, ortools, pyvroom; print('vrpbench', vrpbench.__version__)"
python -m pytest -q
```

`vrpbench 0.1.0` and a quiet pytest run mean the harness and the three heuristic solvers import. `vrpsolvereasy` imports with the rest of the package; it only fails later, at solve time, when the BaPCod library is absent.

The editable install also adds a `vrpbench` command:

```bash
vrpbench --config experiments/smoke.yaml
```

`python -m vrpbench.cli --config experiments/smoke.yaml` is the same entry point.

### Optional: VRPSolverEasy and BaPCod

`VRPSolverEasy` on PyPI is a Python wrapper. The native library (`bapcod-shared.dll` on Windows, `.so` on Linux, `.dylib` on macOS) is distributed separately by the BaPCod project.

1. Download the free build for your operating system from [bapcod.math.u-bordeaux.fr](https://bapcod.math.u-bordeaux.fr/). The free build uses COIN-OR CLP and is enough for CVRP and VRPTW in this harness.
2. Find the empty platform directory inside the virtual environment:

```bash
python -c "import VRPSolverEasy, pathlib; print(pathlib.Path(VRPSolverEasy.__file__).resolve().parent / 'lib')"
```

3. Copy the matching folder from the archive into that `lib` directory:

| Operating system | Folder inside the BaPCod archive | Destination under `lib/` |
| --- | --- | --- |
| Windows | `Windows` | `lib/Windows` |
| Linux | `Linux` | `lib/Linux` |
| macOS | `Darwin` | `lib/Darwin` |

On Windows the destination is usually `.venv\Lib\site-packages\VRPSolverEasy\lib\Windows`. On Linux and macOS it is `.venv/lib/python3.x/site-packages/VRPSolverEasy/lib/<platform>`. Trust the one-liner above if those guesses differ.

4. Check that the library loads:

```bash
python -c "from VRPSolverEasy.src import solver; solver.Model(); print('BaPCod loaded')"
```

Copy Windows binaries only onto Windows, Linux binaries only onto Linux, and the Darwin build only onto macOS. A library built for another operating system, or for the other CPU architecture, fails to load. Details, the academic CPLEX build, and error text are in [BAPCOD_SETUP.md](BAPCOD_SETUP.md).

### Optional: Alkaid-SDVRP

`alkaid_sdvrp` runs the official Alkaid-SDVRP 1.1 executable. This repository does not vendor that source or binary.

Build the `standalone` target from [HUST-Smart/Alkaid-SDVRP](https://github.com/HUST-Smart/Alkaid-SDVRP) with CMake and a C++17 compiler, then point the harness at the executable **in the same terminal** that starts the benchmark.

Windows (PowerShell), after the Rtools 4.4 build described in [ALKAID_SETUP.md](ALKAID_SETUP.md):

```powershell
$env:ALKAID_SDVRP_EXECUTABLE = "C:\path\to\AlkaidSD.exe"
```

Linux and macOS:

```bash
export ALKAID_SDVRP_EXECUTABLE=/path/to/AlkaidSD
```

A value set in another window is invisible to the benchmark. macOS uses the same CMake Release build as Linux; the compiler is the one installed by the Xcode command-line tools.

### Optional: the web studio

The studio and the fueling map need the `web` extra and Node.js 20 or newer. Installation for each operating system is in [web/README.md](web/README.md).

```bash
python -m pip install -e ".[web]"
```

On Windows PowerShell the quotes are required so the square brackets are not treated as a wildcard.

## Run a benchmark

The commands below assume the virtual environment is active. On Windows, `python` then means `.venv\Scripts\python.exe`. On Linux and macOS it means `.venv/bin/python`.

```bash
# CVRP and VRPTW, one small instance each, PyVRP and OR-Tools
python -m vrpbench.cli --config experiments/smoke.yaml

# Multi-depot, PyVRP + OR-Tools + VROOM
python -m vrpbench.cli --config experiments/mdvrp_smoke.yaml

# Mixed pickup and delivery
python -m vrpbench.cli --config experiments/vrpmpd_smoke.yaml

# Periodic VRP
python -m vrpbench.cli --config experiments/pvrp_smoke.yaml

# Split delivery on representative DIMACS R1 instances
python -m vrpbench.cli --config experiments/sdvrp_smoke.yaml
```

Full configs, ten seeds and a 10-second budget per cell, live next to the smoke files:

| Config | What it runs |
| --- | --- |
| `experiments/benchmark.yaml` | CVRP X-set and Solomon VRPTW. PyVRP, OR-Tools, VROOM, VRPSolverEasy. |
| `experiments/mdvrp_benchmark.yaml` | Cordeau MDVRP. PyVRP, OR-Tools, VROOM. |
| `experiments/vrpmpd_benchmark.yaml` | Salhi–Nagy mixed pickup and delivery. |
| `experiments/pvrp_benchmark.yaml` | Cordeau periodic instances. |
| `experiments/sdvrp_benchmark.yaml` | All 95 DIMACS R1 instances. AASA-PyVRP, AASA-VROOM, Alkaid. |

Each full config appends to the same `results/results.csv`, so run them one after another. On Linux and macOS, `run_all_benchmarks.sh` does that in the order above.

```bash
chmod +x run_all_benchmarks.sh          # once, after cloning
./run_all_benchmarks.sh                 # Linux: one worker per core
./run_all_benchmarks.sh --threads 8
./run_all_benchmarks.sh --threads 8 --force
```

On macOS, pass `--threads` (see [Installation](#macos)). The script looks for `.venv/bin/python`, then `python3`, then `python`, prints a timestamped header per config, and exits non-zero if any config fails.

On Windows PowerShell, the same sequence is:

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py -m vrpbench.cli --config experiments/benchmark.yaml --threads 8
& $py -m vrpbench.cli --config experiments/vrpmpd_benchmark.yaml --threads 8
& $py -m vrpbench.cli --config experiments/sdvrp_benchmark.yaml --threads 8
& $py -m vrpbench.cli --config experiments/pvrp_benchmark.yaml --threads 8
& $py -m vrpbench.cli --config experiments/mdvrp_benchmark.yaml --threads 8
```

## Results, resume, and parallel runs

Each finished cell appends one row to `results/results.csv`. A crash keeps every row already written. The columns that matter for a comparison are:

| Column | Meaning |
| --- | --- |
| `status` | `ok`, `infeasible`, or `error`. |
| `objective` | Distance recomputed by the harness. |
| `gap_pct` | Gap to the best-known value, when one is on file. |
| `feasible` | Whether the independent checks passed. |
| `runtime_s` | Wall-clock time of that solve. |
| `num_vehicles` | Routes used. |
| `obj_mismatch` | Solver-reported cost minus the recomputed cost. |
| `error` | Exception text when `status` is `error`. |

Set `store_detail: true` in the YAML to also write per-run JSON, including routes, under the results directory.

### Resume

A second launch of the same config reads the CSV and skips cells that already have a row.

```bash
python -m vrpbench.cli --config experiments/benchmark.yaml --threads 8
```

The startup line reports the skip, for example: `Resume: 1430/1600 cells already in results/results.csv; running 170 remaining.`

A cell is the tuple `(run_id, instance_name, variant, solver, seed)`. Solver version and time budget are not part of the key, and a row from another `run_id` does not block the current experiment. Any status counts as done, including `error`. To solve a cell again, pass `--force` (alias `--no-resume`) or delete its row. `--force` appends new rows; it does not clear the file. To start from an empty table, point `results_dir` at a new folder or delete the CSV.

### Parallel cells

`--threads N` (alias `-j N`) runs up to `N` cells at once, each in its own process. The default is `1`.

```bash
python -m vrpbench.cli --config experiments/benchmark.yaml --threads 8
```

Each worker still receives the full `time_budget_s`. Keep `N` at or below the number of physical cores; the CLI warns when `N` exceeds `os.cpu_count()`. With more than one thread, rows arrive in completion order. The set of rows matches a sequential run. An exception in one cell is stored as `status=error` and the rest of the grid continues.

## Reports

`python-docx` is installed with the harness. Two scripts turn the CSV into a landscape A4 Word report, one table per variant:

```bash
python scripts/aggregate.py
python scripts/generate_report.py
```

`scripts/aggregate.py` reads `results/results.csv` and writes `results/table_data.json`. For each instance and solver it averages objective, gap, runtime, and vehicle count over the seeds whose status is `ok`, and records how many of those seeds succeeded. Instance names are normalised so a path and a bare filename for the same file collapse to one row.

`scripts/generate_report.py` reads that JSON and writes `results/vrp_benchmark_report.docx`. Solver groups are separated by a heavy rule and a stable colour (PyVRP blue, OR-Tools orange, VROOM green, VRPSolverEasy purple, Alkaid red). In each row the best value of a comparable metric is set in bold on a lighter tint of that solver's colour. An em dash marks a solver with no successful run.

Run the two scripts again after the CSV changes. Both outputs stay in `results/`.

## Experiment configuration

```yaml
run_id: baseline          # optional; default is a timestamp
seeds: [0, 1, 2]          # one cell per seed
time_budget:
  base_s: 10              # seconds per cell
  per_node_ms: 0          # extra milliseconds per node; 0 keeps the budget flat
solvers: [pyvrp, ortools, vroom, vrpsolvereasy]
store_detail: false       # true also writes per-run JSON
results_dir: results
datasets:
  - variant: CVRP
    instances:
      - data/instances/X/X-n101-k25.vrp
  - variant: VRPTW
    instances:
      - data/instances/Solomon/C101.txt
  - variant: MDVRP         # required: these files share the .txt extension with Solomon
    instances:
      - data/instances/MDVRP/old/p01.txt
  - variant: VRPMPD        # also inferred from the .vrpmpd extension
    instances:
      - data/instances/S/CMT01H.vrpmpd
  - variant: PVRP          # required, same reason as MDVRP
    instances:
      - data/instances/PVRP/old/p01.txt
  - variant: SDVRP
    instances:
      - data/instances/SDVRP_R1_instances/SET-1/SD1.txt
```

Declare `variant: MDVRP` or `variant: PVRP` on every `.txt` group of that kind. The extension is shared with Solomon VRPTW, so the extension alone is not enough. SDVRP R1 is recognised from `.sd`, `.cri`, and R1-shaped `.txt` files; writing `variant: SDVRP` is valid too.

`vrpsolvereasy` is rejected if it appears in an MDVRP, VRPMPD, PVRP, or SDVRP group. Periodic instances take the names `pvrp_pyvrp`, `pvrp_ortools`, and `pvrp_vroom`. Split-delivery instances take `aasa_pyvrp`, `aasa_vroom`, and `alkaid_sdvrp`. The plain names `pyvrp`, `ortools`, and `vroom` are the single-period solvers.

## Solvers

| Name | Method | CVRP | VRPTW | MDVRP | VRPMPD | PVRP | SDVRP |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `pyvrp` | Heuristic, large neighbourhood search | yes | yes | yes | yes |  |  |
| `ortools` | Heuristic, OR-Tools routing | yes | yes | yes | yes |  |  |
| `vroom` | Heuristic, large neighbourhood search | yes | yes | yes | yes |  |  |
| `vrpsolvereasy` | Exact branch-and-cut-and-price (BaPCod) | yes | yes |  |  |  |  |
| `pvrp_pyvrp` | ALNS over day patterns, PyVRP each day |  |  |  |  | yes |  |
| `pvrp_ortools` | ALNS over day patterns, OR-Tools each day |  |  |  |  | yes |  |
| `pvrp_vroom` | ALNS over day patterns, VROOM each day |  |  |  |  | yes |  |
| `aasa_pyvrp` | AASA split into a CVRP, then PyVRP |  |  |  |  |  | yes |
| `aasa_vroom` | AASA split into a CVRP, then VROOM |  |  |  |  |  | yes |
| `alkaid_sdvrp` | Native Alkaid-SDVRP ILS/RVND |  |  |  |  |  | yes |

OR-Tools ignores the seed. VROOM's AASA wrapper currently ignores the seed as well. `vrpsolvereasy` needs the BaPCod library, accepts instances of at most 1022 nodes, and is only informative when the time budget is long enough for an exact method.

**MDVRP.** PyVRP, OR-Tools, and VROOM all model several depots directly: PyVRP with one vehicle type per depot, OR-Tools with a start and end index per vehicle, and VROOM with a start and end index per vehicle. Assignment is open. The per-depot route-duration field in the Cordeau files is ignored, so every solver runs the capacity-only problem. Each depot is given as many vehicles as there are customers; a good solution uses far fewer.

**VRPMPD.** PyVRP and VROOM carry both a delivery amount and a pickup amount on each stop. OR-Tools uses two routing dimensions that together enforce the same load walk. All three add a large fixed cost per vehicle so the search prefers fewer vehicles first and shorter distance second. The adapter removes that fixed cost before it reports an objective, which keeps `obj_mismatch` near zero.

**PVRP.** The three `pvrp_*` solvers share one ALNS wrapper. The outer search assigns each customer a legal day combination. The inner solver then routes each day on its own, as a CVRP when the instance has no duration limit and as a VRPTW when it does, with at most `m` vehicles that day. The recorded objective is total distance over all days.

**SDVRP.** The target is DIMACS R1: one capacity, integer demands, explicit split quantities, no site-dependent fleet, no route-duration limit, and no hard cap on the number of vehicles. `aasa_pyvrp` and `aasa_vroom` build a CVRP of colocated fragments with fixed split parameter `p = 2` and two demand levels, then call the existing adapter. Delivered quantities are restricted to those fragments, so this is an approximation of the full split space. `alkaid_sdvrp` sends the original R1 file to Alkaid and does not use that reduction. Every accepted solution carries `route_deliveries`.

## Datasets and best-known solutions

Instance files live under `data/instances/`.

- **CVRP.** CVRPLIB X-set in `data/instances/X/` (`.vrp`, Euclidean distance rounded to the nearest integer). Best-known values from Uchoa et al. 2017 are included.
- **VRPTW.** Solomon 100-customer set in `data/instances/Solomon/` (`.txt`, classes C1, C2, R1, R2, RC1, RC2). Distance is raw Euclidean.
- **MDVRP.** Cordeau instances in `data/instances/MDVRP/` ([source](http://neumann.hec.ca/chairedistributique/data/)): `old/` uses integer coordinates and `new/` uses floating-point coordinates. Distance is rounded to the nearest integer. Visit-frequency fields used by the periodic variant are discarded.
- **VRPMPD.** Salhi–Nagy S instances in `data/instances/S/` (`.vrpmpd`, [source](http://webhotel4.ruc.dk/~keld/research/LKH-3/)). Each customer is a pure delivery or a pure pickup. The vehicle leaves the depot carrying every delivery on the route; the load then falls at deliveries and rises at pickups, and must stay inside capacity at every stop. Time windows in the files are ignored. The objective is lexicographic: fewer vehicles, then shorter distance. No best-known values are bundled, so `gap_pct` is empty.
- **PVRP.** Cordeau instances in `data/instances/PVRP/` ([source](http://neumann.hec.ca/chairedistributique/data/)): `old/p01`–`p32` have no route-duration limit, and `new/pr01`–`pr10` have one. Each customer has a visit frequency and a list of allowed day combinations. At most `m` routes run on a given day. Distance is rounded to the nearest integer. The objective is total distance across days, with no vehicle-count term. No best-known values are bundled.
- **SDVRP.** DIMACS R1 in `data/instances/SDVRP_R1_instances/` (`.txt`, `.sd`, `.cri`; [source](http://dimacs.rutgers.edu/programs/challenge/vrp/vrpsd)): 95 instances in four sets. The file is `n Q`, one line of `n` demands, then `n + 1` coordinate rows with the depot first. Distance is `floor(sqrt(dx² + dy²) + 0.5)`. Official best-known values are bundled, so `gap_pct` is filled in.

`data/bks.csv` stores `instance_name`, `variant`, `bks_value`, `rounding`, and `source`. The `rounding` column records the convention the published value used (`int` for CVRP, float for VRPTW), and the loader follows that convention. A missing best-known value leaves `gap_pct` blank. That is the normal outcome for MDVRP, VRPMPD, and PVRP.

## How solutions are checked

Every solution is scored again from the instance distance matrix, then checked:

- **CVRP and MDVRP.** Every customer is visited once, no depot appears inside a route, and route load is at most capacity. MDVRP also requires `route_depots` to name a real depot for each route, and the route is scored from that depot.
- **VRPTW.** The CVRP checks, plus time-window compliance at every stop.
- **VRPMPD.** Every customer is visited once. The load walk starts at the sum of deliveries on the route, drops at a delivery, rises at a pickup, and must stay inside `[0, capacity]` after every stop.
- **PVRP.** Each route carries a day. The days a customer is visited must equal one allowed combination. At most `m` routes run per day. Route load is at most capacity. On the new set, travel plus service on a route stays within `max_route_duration`. Distance is summed across days from the harness matrix.
- **SDVRP.** `route_deliveries` is required. Its keys match the customers on that route, every quantity is positive, route load is at most the single capacity, and the quantities delivered to a customer sum to that customer's demand.

## Repository layout

```text
vrpbench/           harness packages (core, datasets, solvers, runner, results)
web/                FastAPI service and the Vite studio
experiments/        smoke and full YAML configs
data/instances/     benchmark files
data/bks.csv        best-known values
scripts/            aggregate.py and generate_report.py
tests/              pytest suite
results/            created when a benchmark runs
```

## Tests

```bash
python -m pytest -q
```

Tests that need the BaPCod library, or a live Alkaid executable, are skipped when that binary is absent, so the default suite stays green. The smoke configs under `experiments/*_smoke.yaml` are the short end-to-end check once the install above succeeds.
