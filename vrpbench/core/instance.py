"""Unified VRP instance representation for CVRP and VRPTW.

A single :class:`Instance` type covers both variants. VRPTW-only fields
(``time_windows``, ``service_times``) are ``None`` for CVRP. The precomputed
``distance`` matrix is the authoritative source for every objective/gap
computation, which keeps results internally consistent regardless of external
rounding conventions.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

CVRP = "CVRP"
VRPTW = "VRPTW"
VARIANTS = (CVRP, VRPTW)


@dataclass(frozen=True)
class Instance:
    """A capacitated VRP instance, optionally with time windows.

    Node index 0 is the depot. Customer indices are ``1 .. num_nodes - 1``.
    """

    name: str
    variant: str  # "CVRP" | "VRPTW"
    num_nodes: int  # includes the depot
    coords: np.ndarray  # (n, 2) float
    demands: np.ndarray  # (n,) int; depot demand is 0
    capacity: int
    distance: np.ndarray  # (n, n) float — precomputed, authoritative
    depot: int = 0
    num_vehicles: int | None = None  # fleet size/cap if specified, else None
    # VRPTW-only (None for CVRP):
    time_windows: np.ndarray | None = None  # (n, 2): [earliest, latest]
    service_times: np.ndarray | None = None  # (n,)
    # Original instance file, when loaded from disk (used by file-based solvers).
    source_path: str | None = None

    def __post_init__(self) -> None:
        if self.variant not in VARIANTS:
            raise ValueError(f"unknown variant {self.variant!r}; expected one of {VARIANTS}")
        n = self.num_nodes
        if self.coords.shape != (n, 2):
            raise ValueError(f"coords must be ({n}, 2), got {self.coords.shape}")
        if self.demands.shape != (n,):
            raise ValueError(f"demands must be ({n},), got {self.demands.shape}")
        if self.distance.shape != (n, n):
            raise ValueError(f"distance must be ({n}, {n}), got {self.distance.shape}")
        if self.variant == VRPTW:
            if self.time_windows is None or self.service_times is None:
                raise ValueError("VRPTW instance requires time_windows and service_times")
            if self.time_windows.shape != (n, 2):
                raise ValueError(f"time_windows must be ({n}, 2), got {self.time_windows.shape}")
            if self.service_times.shape != (n,):
                raise ValueError(f"service_times must be ({n},), got {self.service_times.shape}")

    @property
    def customers(self) -> range:
        """Customer indices (everything except the depot)."""
        return range(1, self.num_nodes)
