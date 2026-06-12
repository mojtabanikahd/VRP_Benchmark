# BaPCod Setup for VRPSolverEasy Integration

## Overview

The `vrpsolvereasy` solver adapter in vrpbench requires the **BaPCod shared library** (`bapcod-shared.dll` on Windows, `.so` on Linux, `.dylib` on macOS) to function. The Python package `VRPSolverEasy` (installed via `pip`) is only the wrapper; the native solver binaries are **not included** in the wheel and must be provisioned separately.

This document explains why, where to get them, and how to set them up.

---

## Why BaPCod is Separate

- The `VRPSolverEasy` wheel (`py3-none-any`, ~3 MB) is platform-agnostic and contains only Python source and demo data.
- The BaPCod binaries (VRPSolver + COIN-OR CLP, ~7 MB per platform) are compiled separately and must be added post-install.
- This design allows academic users with CPLEX licenses to use a different compiled variant without re-downloading the entire package.

**Without the BaPCod binaries, any solve attempt raises:**
```
ModelError: Cannot load or find library bapcod ... correctly installed on your system
```

---

## Where to Get BaPCod

### Free Version (Recommended for Benchmarking)

1. Visit **https://bapcod.math.u-bordeaux.fr/**
2. Navigate to "Download" → "Free version"
3. Select your platform (Windows, Linux, macOS)
4. Download the `.zip` distribution (no registration required for the free version)
5. Extract it

The free version includes COIN-OR CLP as the MIP solver, which is fully functional for CVRP and VRPTW benchmarking.

### Academic Version (Optional)

If you have institutional access to CPLEX and want to use the academic version:
1. Follow the same BaPCod site
2. Request the academic version (requires institutional email)
3. Install CPLEX (free with academic license)
4. Compile BaPCod from source per the BaPCod user guide
5. Use `solver_name="CPLEX"` and `cplex_path="<cplex-install-dir>"` in the adapter

For this project, the **free version is sufficient**.

---

## Installation Steps

### Step 1: Locate Your Virtual Environment

```bash
# In the project root, find where .venv is located:
ls -d .venv
# Output: .venv
```

### Step 2: Identify the Target Directory

The BaPCod binaries must be copied into:
```
<venv>/Lib/site-packages/VRPSolverEasy/lib/<OS>/
```

For example, on Windows in this project:
```
.venv/Lib/site-packages/VRPSolverEasy/lib/Windows/
```

You can verify this directory exists but is empty (except for `__init__.py`):
```bash
ls -la .venv/Lib/site-packages/VRPSolverEasy/lib/Windows/
# Should show only __init__.py
```

### Step 3: Copy BaPCod Binaries

After extracting the BaPCod distribution:

**On Windows:**
```bash
# Extract the BaPCod .zip, then:
cp -r <BaPCod-extract>/Windows/* .venv/Lib/site-packages/VRPSolverEasy/lib/Windows/
```

This copies:
- `bapcod-shared.dll` (~6.4 MB)
- `msvcp140.dll` (MSVC runtime)
- `vcruntime140.dll`, `vcruntime140_1.dll` (MSVC runtime)

**On Linux:**
```bash
cp -r <BaPCod-extract>/Linux/* .venv/Lib/site-packages/VRPSolverEasy/lib/Linux/
```

**On macOS:**
```bash
cp -r <BaPCod-extract>/Darwin/* .venv/Lib/site-packages/VRPSolverEasy/lib/Darwin/
```

### Step 4: Verify the Installation

Run a quick test:
```bash
python -c "from VRPSolverEasy.src import solver; m = solver.Model(); print('BaPCod loaded successfully')"
```

Or run the full test suite:
```bash
pytest tests/test_vrpsolvereasy_solver.py -v
```

If you see `ModelError: Cannot load or find library bapcod`, the binaries were not copied to the correct location — check Step 2 again.

---

## Why This is Not Automated

- **License compliance:** Distributing BaPCod binaries requires respecting its license (free version is permissive; academic version has restrictions).
- **Git size:** Binaries (~7 MB) should not be committed to version control. The `.venv` directory is properly git-ignored to prevent accidental commits.
- **CI/CD consideration:** On a CI system, either:
  - Use a setup script that downloads and installs BaPCod at test time
  - Cache the installed `.venv` across runs
  - Request BaPCod distribution in CI secret storage (academic version)

For local development, the manual copy-and-verify steps above are simple and take ~30 seconds.

---

## Troubleshooting

### Error: "Cannot load or find library bapcod"
- **Cause:** Binaries not copied or in wrong location.
- **Fix:** Re-verify the path in Step 2 and repeat Step 3. Check that `bapcod-shared.dll` (or `.so`/`.dylib`) exists in the target directory with `ls` or `dir`.

### Error: "ImportError: cannot import name 'Model' from VRPSolverEasy.src"
- **Cause:** `VRPSolverEasy` package not installed.
- **Fix:** Run `pip install -r requirements.txt` in the project root.

### Error: "Incompatible architecture" or segfault on solve
- **Cause:** Wrong OS binaries copied (e.g., Linux binaries on Windows).
- **Fix:** Download the correct BaPCod distribution for your OS and re-copy to the correct `lib/<OS>` subdirectory.

---

## References

- BaPCod project: https://bapcod.math.u-bordeaux.fr/
- VRPSolverEasy PyPI: https://pypi.org/project/VRPSolverEasy/
- Solver adapter: [vrpbench/solvers/vrpsolvereasy_solver.py](vrpbench/solvers/vrpsolvereasy_solver.py)
- Test suite: [tests/test_vrpsolvereasy_solver.py](tests/test_vrpsolvereasy_solver.py)
