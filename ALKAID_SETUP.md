# Alkaid-SDVRP setup

`alkaid_sdvrp` uses the official Alkaid-SDVRP v1.1 executable. The benchmark
repository intentionally does not vendor the upstream C++ source or a binary.

Official sources:

- https://github.com/HUST-Smart/Alkaid-SDVRP
- https://github.com/INFORMSJoC/2024.0606
- https://doi.org/10.1287/ijoc.2024.0606

Clone or download the pinned v1.1/archive source outside this repository, then
build its standalone target:

```powershell
cmake -S standalone -B build/standalone
cmake --build build/standalone --config Release
$env:ALKAID_SDVRP_EXECUTABLE = "C:\path\to\AlkaidSD.exe"
```

On a single-configuration Linux generator, the same build is typically:

```bash
cmake -S standalone -B build/standalone -DCMAKE_BUILD_TYPE=Release
cmake --build build/standalone
export ALKAID_SDVRP_EXECUTABLE=/path/to/AlkaidSD
```

The adapter records `alkaid-v1.1` plus a short SHA-256 executable fingerprint in
the solver version. For each benchmark cell it creates a temporary INI and JSON
output path, but passes `Instance.source_path`—the original DIMACS R1 instance—
unchanged as Alkaid's input. It overrides only input, output, seed, and time limit
from the documented default configuration, captures process diagnostics, and
independently decodes and evaluates reported delivery quantities.
