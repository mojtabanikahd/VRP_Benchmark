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

from vrpbench.core.instance import CVRP, MDVRP, VRPTW, VRPMPD, Instance

# Map file extension -> (vrplib format, our variant).
_EXT_FORMAT = {
    ".vrp": ("vrplib", CVRP),
    ".txt": ("solomon", VRPTW),
    ".vrpmpd": ("vrpmpd", VRPMPD),
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

    MDVRP files share the ``.txt`` extension with Solomon VRPTW, so MDVRP cannot
    be inferred from the extension — it must be requested explicitly via
    ``variant=MDVRP``, which dispatches to the Cordeau parser below.
    VRPMPD files use the unique ``.vrpmpd`` extension and are dispatched
    automatically (no explicit ``variant`` needed).
    """
    if variant == MDVRP:
        return _load_cordeau_mdvrp(path)
    if Path(path).suffix.lower() == ".vrpmpd":
        if variant is not None and variant != VRPMPD:
            raise ValueError(
                f"{path}: declared variant {variant!r} but file extension is .vrpmpd"
            )
        return _load_vrpmpd(path)

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


def _load_cordeau_mdvrp(path: str | os.PathLike) -> Instance:
    """Parse a Cordeau MDVRP instance (``http://neumann.hec.ca/chairedistributique``).

    Layout (whitespace-separated; see CLAUDE.md §1):

        type  m  n  t              # type (ignore), m vehicles/depot (ignore),
                                   # n customers, t depots
        D_i Q_i        x t         # per depot: max route duration (IGNORED), capacity
        id x y svc dem ...         # n customer lines; trailing PVRP fields dropped
        id x y ...     x t         # t depot coordinate lines (at end of file)

    The ``t`` depots are placed first at internal indices ``0 .. t-1`` and the
    ``n`` customers follow at ``t .. t+n-1`` (so the result matches the rest of the
    codebase, which expects depots before customers). Coordinates are read as
    floats, covering both the integer ``old`` and float ``new`` instance sets. The
    distance matrix is the full Euclidean matrix over all nodes (authoritative).
    Max route duration ``D`` is ignored (capacity-constrained MDVRP).
    """
    tokens = iter(Path(path).read_text(encoding="utf-8").split())

    next(tokens)  # type (e.g. 2 = MDVRP) — ignored
    next(tokens)  # m = vehicles per depot — ignored (generous fleet decided by solvers)
    num_customers = int(next(tokens))
    num_depots = int(next(tokens))

    capacity = None
    for _ in range(num_depots):
        next(tokens)  # D = max route duration — ignored
        cap = int(next(tokens))  # Q = vehicle capacity (homogeneous across depots)
        capacity = cap if capacity is None else capacity

    # Customer lines: id, x, y, service (ignored), demand, then 6 PVRP tokens (dropped).
    cust_coords: list[tuple[float, float]] = []
    cust_demands: list[int] = []
    for _ in range(num_customers):
        next(tokens)  # id (file-local, ignored)
        cx = float(next(tokens))
        cy = float(next(tokens))
        next(tokens)  # service time — ignored (no time windows in this MDVRP build)
        cust_demands.append(int(float(next(tokens))))
        cust_coords.append((cx, cy))
        for _ in range(6):  # PVRP visit-frequency / day-combination metadata
            next(tokens)

    # Depot coordinate lines: id, x, y, then 4 trailing tokens (dropped).
    depot_coords: list[tuple[float, float]] = []
    for _ in range(num_depots):
        next(tokens)  # id (file-local, ignored)
        dx = float(next(tokens))
        dy = float(next(tokens))
        depot_coords.append((dx, dy))
        for _ in range(4):
            next(tokens)

    # Depots first (indices 0..t-1), then customers (t..t+n-1).
    coords = np.asarray(depot_coords + cust_coords, dtype=float)
    n = coords.shape[0]
    demands = np.asarray([0] * num_depots + cust_demands, dtype=int)

    # Euclidean distances rounded to the nearest integer — the same EUC_2D
    # convention vrplib applies to CVRP. The solvers all optimise over integers
    # (scale 1), so making the authoritative matrix integer keeps the four solvers
    # byte-identical and the evaluator's re-score matches (obj_mismatch ~ 0).
    diff = coords[:, None, :] - coords[None, :, :]
    distance = np.rint(np.sqrt((diff**2).sum(axis=2)))

    return Instance(
        name=Path(path).stem,
        variant=MDVRP,
        num_nodes=n,
        coords=coords,
        demands=demands,
        capacity=int(capacity),
        distance=distance,
        depot=0,
        depot_indices=tuple(range(num_depots)),
        num_vehicles=None,
        source_path=str(path),
    )


def _load_vrpmpd(path: str | os.PathLike) -> Instance:
    """Parse a VRPMPD instance in the LKH-3 / Salhi-Nagy `.vrpmpd` format.

    Layout (section-based; depot is always file node id 1 = internal index 0):

        NAME : <name>
        DIMENSION : <n>      # total nodes incl. depot
        VEHICLES : <k>       # fleet hint (not a hard cap)
        CAPACITY : <Q>
        EDGE_WEIGHT_TYPE : EXACT_2D
        NODE_COORD_SECTION
        <id> <x> <y>         # DIMENSION lines, 1-indexed
        PICKUP_AND_DELIVERY_SECTION
        <id> <demand> <early> <late> <service> <pickup> <delivery>
                             # fields 6 and 7 are used; others ignored
        DEPOT_SECTION
        1                    # depot node id -> internal index 0
        -1
        EOF

    Distance matrix: integer-rounded Euclidean (matches CVRP/MDVRP convention).
    """
    text = Path(path).read_text(encoding="utf-8")
    lines = text.splitlines()

    # --- Parse header key-value pairs -----------------------------------------
    header: dict[str, str] = {}
    section: str | None = None
    coord_lines: list[str] = []
    pd_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped == "EOF":
            continue

        # Detect section headers
        upper = stripped.upper()
        if upper == "NODE_COORD_SECTION":
            section = "coords"
            continue
        if upper == "PICKUP_AND_DELIVERY_SECTION":
            section = "pd"
            continue
        if upper == "DEPOT_SECTION":
            section = "depot"
            continue

        if section is None:
            # Header key : value line
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                header[key.strip().upper()] = val.strip()
        elif section == "coords":
            coord_lines.append(stripped)
        elif section == "pd":
            pd_lines.append(stripped)
        # depot section rows are not needed (always node 1 -> index 0)

    n = int(header["DIMENSION"])
    capacity = int(header["CAPACITY"])
    num_vehicles = int(header["VEHICLES"]) if "VEHICLES" in header else None
    name = header.get("NAME") or Path(path).stem

    # --- Coordinates (1-indexed ids; sort by id to build 0-indexed array) -----
    id_to_coord: dict[int, tuple[float, float]] = {}
    for row in coord_lines:
        parts = row.split()
        node_id, x, y = int(parts[0]), float(parts[1]), float(parts[2])
        id_to_coord[node_id] = (x, y)

    if len(id_to_coord) != n:
        raise ValueError(
            f"{path}: NODE_COORD_SECTION has {len(id_to_coord)} nodes, expected {n}"
        )

    # Build coords in id order; id k -> internal index k-1 (depot id 1 -> 0).
    coords = np.array([id_to_coord[i] for i in range(1, n + 1)], dtype=float)

    # --- Pickup and delivery per node -----------------------------------------
    # field indices: 0=id, 1=demand(ignored), 2=early(ignored), 3=late(ignored),
    #                4=service(ignored), 5=pickup, 6=delivery
    pickups_arr = np.zeros(n, dtype=int)
    deliveries_arr = np.zeros(n, dtype=int)

    for row in pd_lines:
        parts = row.split()
        node_id = int(parts[0])
        pickup = int(parts[5])
        delivery = int(parts[6])
        idx = node_id - 1  # 1-indexed -> 0-indexed
        pickups_arr[idx] = pickup
        deliveries_arr[idx] = delivery

    # Depot (index 0) must have zero pickup and delivery.
    pickups_arr[0] = 0
    deliveries_arr[0] = 0

    # Distance: integer-rounded Euclidean (same convention as CVRP/MDVRP).
    diff = coords[:, None, :] - coords[None, :, :]
    distance = np.rint(np.sqrt((diff**2).sum(axis=2)))

    return Instance(
        name=name,
        variant=VRPMPD,
        num_nodes=n,
        coords=coords,
        demands=deliveries_arr,   # mirrors deliveries for interface compatibility
        capacity=capacity,
        distance=distance,
        depot=0,
        num_vehicles=num_vehicles,
        pickups=pickups_arr,
        deliveries=deliveries_arr,
        source_path=str(path),
    )
