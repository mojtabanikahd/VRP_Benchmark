"""Load CVRPLIB (.vrp) and Solomon/Gehring-Homberger (.txt) instances.

Built on the ``vrplib`` reader, which is the same parser PyVRP uses. Crucially,
``vrplib`` already applies the correct distance convention per format:

* CVRP EUC_2D  -> distances rounded to the nearest integer (CVRPLIB convention,
  matching how the X-set BKS values were computed).
* Solomon/GH   -> raw Euclidean floats (matching Solomon/GH BKS convention).

We adopt ``edge_weight`` as the authoritative ``Instance.distance`` so our
objective/gap is consistent with both the solvers and the published BKS.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import vrplib

from vrpbench.core.instance import CVRP, VRPTW, Instance

# Map file extension -> (vrplib format, our variant).
_EXT_FORMAT = {
    ".vrp": ("vrplib", CVRP),
    ".txt": ("solomon", VRPTW),
}


def detect_format(path: str | os.PathLike) -> tuple[str, str]:
    """Return (vrplib_format, variant) inferred from the file extension."""
    ext = Path(path).suffix.lower()
    if ext not in _EXT_FORMAT:
        raise ValueError(
            f"cannot infer format from extension {ext!r}; "
            f"expected one of {sorted(_EXT_FORMAT)}"
        )
    return _EXT_FORMAT[ext]


def load(path: str | os.PathLike, variant: str | None = None) -> Instance:
    """Load an instance file into the unified :class:`Instance` representation.

    ``variant`` may be passed to override extension-based detection; it must then
    match the detected variant (guards against mislabelled config entries).
    """
    fmt, detected = detect_format(path)
    if variant is not None and variant != detected:
        raise ValueError(
            f"{path}: declared variant {variant!r} but file looks like {detected!r}"
        )

    raw = vrplib.read_instance(str(path), instance_format=fmt)

    coords = np.asarray(raw["node_coord"], dtype=float)
    n = coords.shape[0]
    demands = np.asarray(raw["demand"], dtype=int)
    distance = np.asarray(raw["edge_weight"], dtype=float)
    capacity = int(raw["capacity"])
    name = str(raw.get("name") or Path(path).stem)

    depot = _depot_index(raw)
    num_vehicles = int(raw["vehicles"]) if "vehicles" in raw else None

    time_windows = service_times = None
    if detected == VRPTW:
        time_windows = np.asarray(raw["time_window"], dtype=float)
        service_times = np.asarray(raw["service_time"], dtype=float)

    return Instance(
        name=name,
        variant=detected,
        num_nodes=n,
        coords=coords,
        demands=demands,
        capacity=capacity,
        distance=distance,
        depot=depot,
        num_vehicles=num_vehicles,
        time_windows=time_windows,
        service_times=service_times,
        source_path=str(path),
    )


def _depot_index(raw: dict) -> int:
    """CVRPLIB files carry a 0-indexed depot array; Solomon implies depot 0."""
    depot = raw.get("depot")
    if depot is None:
        return 0
    arr = np.atleast_1d(np.asarray(depot, dtype=int))
    return int(arr[0])
