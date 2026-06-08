"""Command-line entrypoint: run a benchmark from an experiment YAML.

Usage:
    python -m vrpbench.cli --config experiments/baseline.yaml
"""

from __future__ import annotations

import argparse
import sys

from vrpbench.runner.config import load_config
from vrpbench.runner.run import run_experiment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vrpbench", description="VRP benchmark runner")
    parser.add_argument("--config", "-c", required=True, help="path to experiment YAML")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    failures = run_experiment(cfg)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
