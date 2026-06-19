#!/usr/bin/env bash
# run_all_benchmarks.sh — run all five VRP benchmark configs sequentially.
#
# Each experiment appends to the shared results/results.csv, so they cannot
# safely run in parallel; --threads controls intra-experiment parallelism only.
#
# Usage:
#   ./run_all_benchmarks.sh                  # threads = nproc
#   ./run_all_benchmarks.sh --threads 4      # explicit thread count
#   ./run_all_benchmarks.sh --force          # re-run all cells (no resume)
#   ./run_all_benchmarks.sh --threads 4 --force
#
set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
THREADS=$(nproc 2>/dev/null || echo 1)
FORCE_FLAG=""

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --threads|-j)
            THREADS="$2"
            shift 2
            ;;
        --threads=*)
            THREADS="${1#*=}"
            shift
            ;;
        --force|--no-resume)
            FORCE_FLAG="--force"
            shift
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Usage: $0 [--threads N] [--force]" >&2
            exit 1
            ;;
    esac
done

if ! [[ "$THREADS" =~ ^[1-9][0-9]*$ ]]; then
    echo "Error: --threads must be a positive integer, got: $THREADS" >&2
    exit 1
fi

# ── Experiment configs (order: largest/longest first for better resume) ───────
CONFIGS=(
    "experiments/benchmark.yaml"
    "experiments/vrpmpd_benchmark.yaml"
    "experiments/sdvrp_benchmark.yaml"
    "experiments/pvrp_benchmark.yaml"
    "experiments/mdvrp_benchmark.yaml"
)

# ── Resolve python interpreter ─────────────────────────────────────────────────
if [[ -x ".venv/bin/python" ]]; then
    PYTHON=".venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v python &>/dev/null; then
    PYTHON="python"
else
    echo "Error: no Python interpreter found." >&2
    exit 1
fi

# ── Run ───────────────────────────────────────────────────────────────────────
TOTAL=${#CONFIGS[@]}
FAILED=()
START_ALL=$(date +%s)

echo "============================================================"
echo "VRP benchmark suite  —  $(date)"
echo "Python   : $PYTHON"
echo "Threads  : $THREADS"
echo "Resume   : $([ -z "$FORCE_FLAG" ] && echo yes || echo no)"
echo "Configs  : $TOTAL"
echo "============================================================"
echo

for i in "${!CONFIGS[@]}"; do
    CFG="${CONFIGS[$i]}"
    IDX=$((i + 1))
    echo "------------------------------------------------------------"
    echo "[$IDX/$TOTAL]  $CFG  —  $(date)"
    echo "------------------------------------------------------------"

    START=$(date +%s)
    # shellcheck disable=SC2086
    if "$PYTHON" -m vrpbench.cli --config "$CFG" --threads "$THREADS" $FORCE_FLAG; then
        END=$(date +%s)
        echo "[$IDX/$TOTAL]  OK  ($(( END - START ))s)"
    else
        END=$(date +%s)
        echo "[$IDX/$TOTAL]  FAILED  ($(( END - START ))s)" >&2
        FAILED+=("$CFG")
    fi
    echo
done

END_ALL=$(date +%s)
echo "============================================================"
echo "Finished  —  $(date)"
echo "Total time: $(( END_ALL - START_ALL ))s"

if [[ ${#FAILED[@]} -gt 0 ]]; then
    echo "FAILED configs (${#FAILED[@]}):"
    for f in "${FAILED[@]}"; do
        echo "  - $f"
    done
    exit 1
else
    echo "All $TOTAL configs completed successfully."
    exit 0
fi
