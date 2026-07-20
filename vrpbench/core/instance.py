"""Unified VRP instance representation for CVRP, VRPTW and MDVRP.

A single :class:`Instance` type covers all variants. VRPTW-only fields
(``time_windows``, ``service_times``) are ``None`` for CVRP/MDVRP. MDVRP carries
multiple depots in ``depot_indices`` (CVRP/VRPTW leave it ``None`` and use the
single ``depot``). The precomputed ``distance`` matrix is the authoritative
source for every objective/gap computation, which keeps results internally
consistent regardless of external rounding conventions.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

CVRP = "CVRP"
VRPTW = "VRPTW"
MDVRP = "MDVRP"
VRPMPD = "VRPMPD"
PVRP = "PVRP"
SDVRP = "SDVRP"
VARIANTS = (CVRP, VRPTW, MDVRP, VRPMPD, PVRP, SDVRP)


@dataclass(frozen=True)
class Instance:
    """A capacitated VRP instance, optionally with time windows or multiple depots.

    Single-depot variants (CVRP/VRPTW/VRPMPD) use node index 0 as the depot with
    customer indices ``1 .. num_nodes - 1``. MDVRP places the ``t`` depots first at
    the contiguous indices ``0 .. t - 1`` (``depot_indices``) and customers at
    ``t .. num_nodes - 1``.

    For VRPMPD, ``pickups`` and ``deliveries`` are the authoritative per-node load
    fields; ``demands`` mirrors ``deliveries`` for interface compatibility with solvers
    that only read ``demands``.
    """

    name: str
    variant: str  # "CVRP" | "VRPTW" | "MDVRP" | "VRPMPD"
    num_nodes: int  # includes all depots and customers
    coords: np.ndarray  # (n, 2) float
    demands: np.ndarray  # (n,) int; depot demand is 0
    capacity: int
    distance: np.ndarray  # (n, n) float — precomputed, authoritative
    depot: int = 0  # primary depot; for MDVRP this is depot_indices[0]
    num_vehicles: int | None = None  # fleet size hint if specified, else None
    # MDVRP-only (None for CVRP/VRPTW/VRPMPD): contiguous depot indices 0..t-1.
    depot_indices: tuple[int, ...] | None = None
    # VRPTW-only (None for CVRP/MDVRP/VRPMPD):
    time_windows: np.ndarray | None = None  # (n, 2): [earliest, latest]
    service_times: np.ndarray | None = None  # (n,)
    # VRPMPD-only (None for CVRP/VRPTW/MDVRP):
    pickups: np.ndarray | None = None    # (n,) int; depot entry is 0
    deliveries: np.ndarray | None = None  # (n,) int; depot entry is 0
    # PVRP-only (None for the other variants):
    periods: int | None = None  # planning horizon t (number of days)
    freq: np.ndarray | None = None  # (n,) int; visits required per node; depot 0
    # per node: list of valid day-combination bitmasks over t days; depot is [].
    combinations: list[list[int]] | None = None
    max_vehicles_per_day: int | None = None  # m; hard cap on routes per day
    max_route_duration: float | None = None  # 0 = unlimited (old set); >0 = new set
    # Legacy SDVRP fields retained only so old detail JSON / imports can deserialize.
    # Canonical SDVRP R1 is homogeneous split delivery and does not populate them.
    num_vehicle_types: int | None = None  # t
    vehicle_capacities: tuple[int, ...] | None = None  # capacity per type (len t)
    vehicle_durations: tuple[float, ...] | None = None  # max duration per type (0 = none)
    vehicles_per_type: int | None = None  # m; hard cap on routes per vehicle type
    allowed_types: list[frozenset[int]] | None = None  # per node, 0-indexed type set
    # Generic optional hard fleet cap, honoured by the CVRP/VRPTW adapter build
    # paths when set. Only PVRP day sub-instances set it (so it never collides with
    # the ``num_vehicles`` hint used by existing variants).
    max_vehicles: int | None = None
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
        if self.variant == MDVRP:
            di = self.depot_indices
            if not di:
                raise ValueError("MDVRP instance requires a non-empty depot_indices")
            if tuple(di) != tuple(range(len(di))):
                raise ValueError(f"depot_indices must be contiguous from 0, got {di}")
            if len(di) >= n:
                raise ValueError(f"depot_indices {di} leaves no customers (num_nodes={n})")
            if self.depot not in di:
                raise ValueError(f"depot {self.depot} must be one of depot_indices {di}")
        if self.variant == VRPMPD:
            if self.pickups is None or self.deliveries is None:
                raise ValueError("VRPMPD instance requires pickups and deliveries arrays")
            if self.pickups.shape != (n,):
                raise ValueError(f"pickups must be ({n},), got {self.pickups.shape}")
            if self.deliveries.shape != (n,):
                raise ValueError(f"deliveries must be ({n},), got {self.deliveries.shape}")
        if self.variant == PVRP:
            if self.periods is None or self.periods < 1:
                raise ValueError("PVRP instance requires periods >= 1")
            if self.max_vehicles_per_day is None or self.max_vehicles_per_day < 1:
                raise ValueError("PVRP instance requires max_vehicles_per_day >= 1")
            if self.freq is None or self.freq.shape != (n,):
                raise ValueError(f"PVRP freq must be ({n},), got {None if self.freq is None else self.freq.shape}")
            if self.combinations is None or len(self.combinations) != n:
                raise ValueError(
                    f"PVRP combinations must have {n} entries, got "
                    f"{None if self.combinations is None else len(self.combinations)}"
                )
            if self.max_route_duration is None or self.max_route_duration < 0:
                raise ValueError("PVRP instance requires max_route_duration >= 0")
            if self.max_route_duration > 0:
                if self.service_times is None or self.service_times.shape != (n,):
                    raise ValueError(
                        "PVRP with a route-duration limit requires service_times of "
                        f"shape ({n},)"
                    )
        if self.variant == SDVRP:
            if self.capacity < 1:
                raise ValueError("SDVRP instance requires capacity >= 1")
            if int(self.demands[0]) != 0:
                raise ValueError("SDVRP depot demand must be 0")
            if any(int(self.demands[c]) < 0 for c in range(1, n)):
                raise ValueError("SDVRP customer demands must be non-negative")

    @property
    def customers(self) -> range:
        """Customer indices (everything except the depot(s))."""
        first = len(self.depot_indices) if self.depot_indices else 1
        return range(first, self.num_nodes)
