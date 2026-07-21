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
$env:Path = "C:\rtools44\x86_64-w64-mingw32.static.posix\bin;" + $env:Path
Remove-Item -Recurse -Force build\standalone
cmake -S standalone -B build/standalone -G Ninja -DCMAKE_CXX_COMPILER=C:/rtools44/x86_64-w64-mingw32.static.posix/bin/g++.exe
cmake --build build/standalone --config Release
$env:ALKAID_SDVRP_EXECUTABLE = "F:\Projects\Forced Military Service\Utilities\Alkaid-SDVRP\build\standalone\AlkaidSD.exe"
```

Set `ALKAID_SDVRP_EXECUTABLE` in the same PowerShell process that launches
`python.exe -m vrpbench.cli`; a value set in another terminal window is not
visible to the benchmark process.

On Windows, make sure the Rtools 4.4 compiler directory appears before older
Rtools paths such as `C:\Rtools\gcc-4.6.3\bin`. Alkaid-SDVRP uses C++17 syntax,
and a stale `build/standalone` CMake cache can keep pointing at the old GCC 4.6.3
compiler. Recreate the build directory after changing compilers.

If you keep a separate verified build directory, set the executable to that path
instead:

```powershell
$env:ALKAID_SDVRP_EXECUTABLE = "F:\Projects\Forced Military Service\Utilities\Alkaid-SDVRP\build\standalone-rtools44\AlkaidSD.exe"
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
