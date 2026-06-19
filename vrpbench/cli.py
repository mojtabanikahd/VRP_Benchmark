"""Command-line entrypoint: run a benchmark from an experiment YAML.

Usage:
    python -m vrpbench.cli --config experiments/baseline.yaml
    python -m vrpbench.cli --config experiments/baseline.yaml --threads 4
"""

from __future__ import annotations

import argparse
import os
import sys

from vrpbench.runner.config import load_config
from vrpbench.runner.run import run_experiment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vrpbench", description="VRP benchmark runner")
    parser.add_argument("--config", "-c", required=True, help="path to experiment YAML")
    parser.add_argument(
        "--threads",
        "-j",
        type=int,
        default=1,
        help="number of parallel worker processes (default: 1 = sequential)",
    )
    args = parser.parse_args(argv)

    if args.threads < 1:
        parser.error(f"--threads must be >= 1, got {args.threads}")
    cpu = os.cpu_count() or 1
    if args.threads > cpu:
        print(
            f"warning: --threads {args.threads} exceeds {cpu} available CPU(s); "
            "cells may contend for cores and per-cell timing may be affected."
        )

    cfg = load_config(args.config)
    failures = run_experiment(cfg, threads=args.threads)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
