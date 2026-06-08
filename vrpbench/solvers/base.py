"""The strict solver interface that makes all solvers interchangeable.

Every solver exposes a single method:

    solve(instance, *, time_budget_s, seed) -> Solution

No solver-specific arguments leak into this signature; engine-specific knobs
live as constructor defaults on the adapter. The runner only ever depends on
this protocol, never on a concrete solver.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from vrpbench.core.instance import Instance
from vrpbench.core.solution import Solution


class SolverError(RuntimeError):
    """Raised when a solver fails to produce a solution."""


@runtime_checkable
class Solver(Protocol):
    name: str
    #: Variants this solver supports, e.g. ("CVRP", "VRPTW").
    supported_variants: tuple[str, ...]

    def solve(self, instance: Instance, *, time_budget_s: float, seed: int) -> Solution:
        """Solve ``instance`` within ``time_budget_s`` wall-clock seconds."""
        ...

    def version(self) -> str:
        """Return the underlying engine version (recorded for reproducibility)."""
        ...
