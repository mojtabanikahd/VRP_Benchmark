"""Adapter for the externally provisioned official Alkaid-SDVRP executable."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Sequence

import numpy as np

from vrpbench.core.evaluate import route_distance
from vrpbench.core.instance import SDVRP, Instance
from vrpbench.core.solution import Solution
from vrpbench.solvers.base import SolverError


_RELEASE = "v1.1"


def _quoted_ini_path(path: Path) -> str:
    value = str(path.resolve())
    if '"' in value:
        raise SolverError(f"Alkaid path contains an unsupported quote: {value!r}")
    return f'"{value}"'


def _config_text(input_path: Path, output_path: Path, seed: int, time_limit: float) -> str:
    """Return the official example configuration with run-specific overrides."""
    return "\n".join(
        [
            f"input = {_quoted_ini_path(input_path)}",
            "input-format = 0",
            f"output = {_quoted_ini_path(output_path)}",
            f"random-seed = {int(seed)}",
            f"time-limit = {float(time_limit):.12g}",
            "blink-rate = 0.021",
            'inter-route-operators = ["Relocate", "Swap<2, 0>", "Swap<2, 1>", "Swap<2, 2>", "Cross", "SwapStar", "SdSwapStar"]',
            'intra-route-operators = ["Exchange", "OrOpt<1>"]',
            'acceptance-criterion = "LAHC"',
            'acceptance-criterion-args = {"length": 83}',
            'ruin-method = "SISRs"',
            'ruin-method-args = {"avg_customers": 36, "max_length": 8, "split_rate": 0.740, "preserved_probability": 0.096}',
            'sorters = {"random": 0.078, "demand": 0.225, "far": 0.942, "close": 0.120}',
            "",
        ]
    )


class AlkaidSDVRPSolver:
    """Invoke Alkaid v1.1 directly on an original DIMACS R1 instance file."""

    name = "alkaid_sdvrp"
    supported_variants = (SDVRP,)

    def __init__(self, executable: str | os.PathLike[str] | Sequence[str] | None = None) -> None:
        self._executable = executable

    def _command(self) -> tuple[str, ...]:
        configured = self._executable
        if configured is None:
            configured = os.environ.get("ALKAID_SDVRP_EXECUTABLE")
        if configured is None or configured == "":
            raise SolverError(
                "Alkaid executable is not configured; set ALKAID_SDVRP_EXECUTABLE"
            )

        if isinstance(configured, (str, os.PathLike)):
            path = Path(configured).expanduser()
            if not path.is_file():
                raise SolverError(f"Alkaid executable does not exist: {path}")
            return (str(path.resolve()),)

        command = tuple(str(part) for part in configured)
        if not command:
            raise SolverError("Alkaid executable command must not be empty")
        executable = Path(command[0]).expanduser()
        if not executable.is_file():
            raise SolverError(f"Alkaid executable does not exist: {executable}")
        return command

    def version(self) -> str:
        executable = Path(self._command()[0])
        digest = hashlib.sha256()
        try:
            with executable.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
        except OSError as exc:
            raise SolverError(f"cannot fingerprint Alkaid executable: {exc}") from exc
        return f"alkaid-{_RELEASE}+sha256:{digest.hexdigest()[:12]}"

    def solve(self, instance: Instance, *, time_budget_s: float, seed: int) -> Solution:
        if instance.variant != SDVRP:
            raise SolverError(f"AlkaidSDVRPSolver does not support {instance.variant!r}")
        if time_budget_s <= 0:
            raise SolverError("Alkaid requires a positive time budget")
        if not instance.source_path:
            raise SolverError("Alkaid requires Instance.source_path for the original R1 file")
        input_path = Path(instance.source_path).expanduser()
        if not input_path.is_file():
            raise SolverError(f"Alkaid source_path does not exist: {input_path}")
        command = self._command()

        start = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="vrpbench-alkaid-") as temp_dir:
            temp_root = Path(temp_dir)
            output_path = temp_root / "solution.json"
            config_path = temp_root / "alkaid.ini"
            config_path.write_text(
                _config_text(input_path, output_path, seed, time_budget_s),
                encoding="utf-8",
            )
            try:
                completed = subprocess.run(
                    [*command, "--config", str(config_path)],
                    capture_output=True,
                    text=True,
                    shell=False,
                    timeout=max(5.0, float(time_budget_s) + 5.0),
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise SolverError(
                    f"Alkaid exceeded its outer timeout after {exc.timeout:.3g}s"
                ) from exc
            except OSError as exc:
                raise SolverError(f"failed to start Alkaid: {exc}") from exc

            if completed.returncode != 0:
                diagnostics = "\n".join(
                    part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
                )
                if len(diagnostics) > 2000:
                    diagnostics = diagnostics[-2000:]
                suffix = f": {diagnostics}" if diagnostics else ""
                raise SolverError(
                    f"Alkaid exited with exit code {completed.returncode}{suffix}"
                )
            if not output_path.is_file():
                raise SolverError("Alkaid did not create the requested JSON output")

            try:
                payload = json.loads(output_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise SolverError(f"Alkaid produced malformed JSON: {exc}") from exc

        routes, deliveries = _decode_json(instance, payload)
        objective = float(sum(route_distance(instance, route) for route in routes))
        return Solution(
            routes=routes,
            objective=objective,
            feasible=True,
            runtime_s=time.perf_counter() - start,
            route_deliveries=deliveries,
        )


def _decode_json(
    instance: Instance, payload: object
) -> tuple[list[list[int]], list[dict[int, int]]]:
    if not isinstance(payload, list):
        raise SolverError("Alkaid JSON root must be a list of routes")

    routes: list[list[int]] = []
    deliveries: list[dict[int, int]] = []
    for route_index, raw_route in enumerate(payload):
        if not isinstance(raw_route, list):
            raise SolverError(f"Alkaid JSON route {route_index} must be a list")
        route: list[int] = []
        delivered: dict[int, int] = {}
        for stop_index, stop in enumerate(raw_route):
            if not isinstance(stop, dict) or set(stop) != {"customer", "quantity"}:
                raise SolverError(
                    f"Alkaid route {route_index} stop {stop_index} must contain customer and quantity"
                )
            customer = stop["customer"]
            quantity = stop["quantity"]
            if isinstance(customer, bool) or not isinstance(customer, (int, np.integer)):
                raise SolverError(f"Alkaid reported invalid customer {customer!r}")
            customer = int(customer)
            if isinstance(quantity, bool) or not isinstance(quantity, (int, np.integer)):
                raise SolverError(
                    f"Alkaid quantity for customer {customer} must be a positive integer"
                )
            quantity = int(quantity)
            if customer == instance.depot:
                if quantity != 0:
                    raise SolverError("Alkaid reported a nonzero depot quantity")
                continue
            if customer not in instance.customers:
                raise SolverError(f"Alkaid reported invalid customer {customer}")
            if quantity <= 0:
                raise SolverError(
                    f"Alkaid quantity for customer {customer} must be a positive integer"
                )
            if customer not in delivered:
                route.append(customer)
                delivered[customer] = 0
            delivered[customer] += quantity
        if route:
            routes.append(route)
            deliveries.append(delivered)

    if not routes and list(instance.customers):
        raise SolverError("Alkaid JSON contains no customer routes")
    return routes, deliveries
