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

from vrpbench.core.instance import CVRP, MDVRP, PVRP, SDVRP, VRPTW, VRPMPD, Instance

# Map file extension -> (vrplib format, our variant).
_EXT_FORMAT = {
    ".vrp": ("vrplib", CVRP),
    ".txt": ("solomon", VRPTW),
    ".vrpmpd": ("vrpmpd", VRPMPD),
    ".sd": ("sdvrp", SDVRP),
    ".cri": ("sdvrp", SDVRP),
}


def detect_format(path: str | os.PathLike) -> tuple[str, str]:
    """Return (vrplib_format, variant) inferred from the file extension."""
    ext = Path(path).suffix.lower()
    if ext == ".txt" and _looks_like_sdvrp_r1(path):
        return ("sdvrp", SDVRP)
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

    MDVRP and PVRP files share the ``.txt`` extension with Solomon VRPTW, so they
    must be requested explicitly. SDVRP R1 is detected from ``.sd`` / ``.cri`` or
    from R1-shaped ``.txt`` content, and explicit ``variant=SDVRP`` is accepted.
    VRPMPD files use the unique ``.vrpmpd`` extension and are dispatched automatically.
    """
    if variant == MDVRP:
        return _load_cordeau_mdvrp(path)
    if variant == PVRP:
        return _load_pvrp(path)
    if variant == SDVRP:
        return _load_sdvrp(path)
    if Path(path).suffix.lower() in {".sd", ".cri"}:
        if variant is not None and variant != SDVRP:
            raise ValueError(
                f"{path}: declared variant {variant!r} but file extension is SDVRP R1"
            )
        return _load_sdvrp(path)
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
    if detected == SDVRP:
        return _load_sdvrp(path)

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


def _looks_like_sdvrp_r1(path: str | os.PathLike) -> bool:
    try:
        lines = [
            ln.split()
            for ln in Path(path).read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
    except OSError:
        return False
    if len(lines) < 3 or len(lines[0]) != 2:
        return False
    try:
        n = int(lines[0][0])
        int(lines[0][1])
    except ValueError:
        return False
    if n < 1 or len(lines) != n + 3 or len(lines[1]) != n:
        return False
    try:
        [int(float(x)) for x in lines[1]]
        for row in lines[2:]:
            if len(row) != 2:
                return False
            float(row[0])
            float(row[1])
    except ValueError:
        return False
    return True


def _load_cordeau_mdvrp(path: str | os.PathLike) -> Instance:
    """Parse a Cordeau MDVRP instance (``http://neumann.hec.ca/chairedistributique``).

    Layout (whitespace-separated; see CLAUDE.md Â§1):

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

    next(tokens)  # type (e.g. 2 = MDVRP) â€” ignored
    next(tokens)  # m = vehicles per depot â€” ignored (generous fleet decided by solvers)
    num_customers = int(next(tokens))
    num_depots = int(next(tokens))

    capacity = None
    for _ in range(num_depots):
        next(tokens)  # D = max route duration â€” ignored
        cap = int(next(tokens))  # Q = vehicle capacity (homogeneous across depots)
        capacity = cap if capacity is None else capacity

    # Customer lines are VARIABLE WIDTH: id, x, y, service (ignored), demand,
    # frequency, then ncombi depot-combination codes (all dropped â€” every depot is
    # eligible in this MDVRP build). ncombi == t, so it differs per instance; reading a
    # fixed count misaligns the token stream (too few â†’ silent corruption, too many â†’
    # StopIteration). Read ncombi from the line and skip exactly that many codes.
    cust_coords: list[tuple[float, float]] = []
    cust_demands: list[int] = []
    for _ in range(num_customers):
        next(tokens)  # id (file-local, ignored)
        cx = float(next(tokens))
        cy = float(next(tokens))
        next(tokens)  # service time â€” ignored (no time windows in this MDVRP build)
        cust_demands.append(int(float(next(tokens))))
        cust_coords.append((cx, cy))
        next(tokens)  # frequency â€” always 1 for MDVRP
        for _ in range(int(float(next(tokens)))):  # ncombi depot-combination codes
            next(tokens)

    # Depot coordinate lines share the same variable-width layout (ncombi is 0 here, so
    # no codes follow), but parse it the same way to stay robust.
    depot_coords: list[tuple[float, float]] = []
    for _ in range(num_depots):
        next(tokens)  # id (file-local, ignored)
        dx = float(next(tokens))
        dy = float(next(tokens))
        depot_coords.append((dx, dy))
        next(tokens)  # service time â€” ignored
        next(tokens)  # demand â€” depots carry none
        next(tokens)  # frequency
        for _ in range(int(float(next(tokens)))):  # ncombi codes (0 for depots)
            next(tokens)

    # Depots first (indices 0..t-1), then customers (t..t+n-1).
    coords = np.asarray(depot_coords + cust_coords, dtype=float)
    n = coords.shape[0]
    demands = np.asarray([0] * num_depots + cust_demands, dtype=int)

    # Euclidean distances rounded to the nearest integer â€” the same EUC_2D
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


def _load_pvrp(path: str | os.PathLike) -> Instance:
    """Parse a Cordeau Periodic VRP instance (``http://neumann.hec.ca/chairedistributique``).

    Layout (whitespace-separated; see CLAUDE.md):

        type  m  n  t              # type (ignore), m vehicles/day, n customers,
                                   # t planning periods (days)
        maxdur  cap                # repeated t times (uniform across days)
        0  x y  svc dem  0 0       # depot is node id 0 FIRST (demand/freq 0)
        i  x y  svc dem  f K c1..cK  # n customers, ids 1..n; K = number of valid
                                   # day-combination bitmasks, then the K codes

    Unlike the MDVRP layout, the depot is the *first* data line (internal index 0)
    and each customer line is variable-width (``7 + K`` tokens), so the file is read
    as a flat token stream: read ``freq`` and ``K``, then exactly ``K`` combination
    codes. Coordinates are read as floats (covers integer ``old`` and float ``new``
    sets) and the distance matrix is integer-rounded Euclidean over all nodes â€” the
    same EUC_2D convention used for CVRP/MDVRP/VRPMPD, keeping the solvers
    byte-identical (scale 1) and the evaluator's re-score consistent.
    """
    tokens = iter(Path(path).read_text(encoding="utf-8").split())

    next(tokens)  # type â€” ignored
    max_vehicles_per_day = int(next(tokens))  # m vehicles per day (hard cap)
    num_customers = int(next(tokens))
    periods = int(next(tokens))

    capacity = None
    max_route_duration = None
    for _ in range(periods):
        dur = float(next(tokens))  # max route duration (0 = unlimited)
        cap = int(next(tokens))    # vehicle capacity (uniform across days)
        capacity = cap if capacity is None else capacity
        max_route_duration = dur if max_route_duration is None else max_route_duration

    # Depot (id 0) + n customers (ids 1..n) = n + 1 data lines.
    num_nodes = num_customers + 1
    coords: list[tuple[float, float]] = []
    demands: list[int] = []
    services: list[float] = []
    freqs: list[int] = []
    combinations: list[list[int]] = []
    for _ in range(num_nodes):
        next(tokens)  # node id (file-local, sequential 0..n; ignored)
        x = float(next(tokens))
        y = float(next(tokens))
        svc = float(next(tokens))
        dem = int(float(next(tokens)))
        freq = int(float(next(tokens)))
        k = int(float(next(tokens)))
        combos = [int(float(next(tokens))) for _ in range(k)]
        coords.append((x, y))
        demands.append(dem)
        services.append(svc)
        freqs.append(freq)
        combinations.append(combos)

    coords_arr = np.asarray(coords, dtype=float)
    diff = coords_arr[:, None, :] - coords_arr[None, :, :]
    distance = np.rint(np.sqrt((diff**2).sum(axis=2)))

    return Instance(
        name=Path(path).stem,
        variant=PVRP,
        num_nodes=num_nodes,
        coords=coords_arr,
        demands=np.asarray(demands, dtype=int),
        capacity=int(capacity),
        distance=distance,
        depot=0,
        num_vehicles=None,
        service_times=np.asarray(services, dtype=float),
        periods=periods,
        freq=np.asarray(freqs, dtype=int),
        combinations=combinations,
        max_vehicles_per_day=max_vehicles_per_day,
        max_route_duration=float(max_route_duration),
        source_path=str(path),
    )


def _load_sdvrp(path: str | os.PathLike) -> Instance:
    """Parse a DIMACS R1 Split Delivery VRP instance."""
    p = Path(path)
    lines = [ln.split() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if len(lines) < 3 or len(lines[0]) != 2:
        raise ValueError(f"{path}: SDVRP R1 header must be 'n Q'")
    try:
        num_customers = int(lines[0][0])
        capacity = int(lines[0][1])
    except ValueError as exc:
        raise ValueError(f"{path}: SDVRP R1 header must contain integers") from exc
    if num_customers < 1 or capacity < 1:
        raise ValueError(f"{path}: SDVRP R1 requires n >= 1 and Q >= 1")
    if len(lines) != num_customers + 3:
        raise ValueError(
            f"{path}: expected {num_customers + 3} non-empty lines, got {len(lines)}"
        )
    if len(lines[1]) != num_customers:
        raise ValueError(
            f"{path}: demand line has {len(lines[1])} values, expected {num_customers}"
        )
    try:
        demands = [0] + [int(float(x)) for x in lines[1]]
        coords: list[tuple[float, float]] = []
        for row in lines[2:]:
            if len(row) != 2:
                raise ValueError("coordinate rows must have exactly two values")
            coords.append((float(row[0]), float(row[1])))
    except ValueError as exc:
        raise ValueError(f"{path}: invalid numeric value in SDVRP R1 file") from exc

    coords_arr = np.asarray(coords, dtype=float)
    diff = coords_arr[:, None, :] - coords_arr[None, :, :]
    distance = np.floor(np.sqrt((diff**2).sum(axis=2)) + 0.5)

    return Instance(
        name=Path(path).stem,
        variant=SDVRP,
        num_nodes=num_customers + 1,
        coords=coords_arr,
        demands=np.asarray(demands, dtype=int),
        capacity=capacity,
        distance=distance,
        depot=0,
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
