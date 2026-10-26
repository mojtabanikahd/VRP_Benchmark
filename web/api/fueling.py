"""Road-network fueling scenarios.

The fueling tab is a single-depot VRPTW: machines need an integer number of
liters inside a refueling window, and driving durations enforce those windows.
Studio reuses the same map and fleet, but only VRPTW keeps the clock. CVRP is
one depot and capacity; MDVRP adds depots and still ignores time. OpenStreetMap
driving distances (kilometers) are the objective. Solved routes are drawn from
OSRM's full road geometry, never from straight chords.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, Field, field_validator

from vrpbench.core import evaluate
from vrpbench.core.instance import CVRP, MDVRP, VRPTW, Instance
from vrpbench.solvers import get_solver
from vrpbench.solvers.base import SolverError

FUEL_SOLVERS = ("pyvrp", "ortools")
FUEL_VARIANTS = (CVRP, VRPTW, MDVRP)
FuelVariant = Literal["CVRP", "VRPTW", "MDVRP"]
_MAX_MACHINES = 99
_DAY_MINUTES = 24 * 60
_METERS_PER_KM = 1000.0
_WINDOW_ERROR = "No schedule meets the refueling windows"
_CLOCK_EPS = 1e-6


class FuelError(ValueError):
    """A fueling scenario cannot be solved."""


class FuelType(BaseModel):
    id: str
    name: str

    @field_validator("id", "name")
    @classmethod
    def _text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("must not be empty")
        return text


class TankerType(FuelType):
    capacity_l: int = Field(ge=1)


class FuelDepot(BaseModel):
    name: str
    lat: float
    lng: float
    window_open_min: float = 0
    window_close_min: float = _DAY_MINUTES

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("name must not be empty")
        return text


class FuelMachine(BaseModel):
    name: str
    machine_type_id: str
    lat: float
    lng: float
    fuel_l: int = Field(ge=1)
    window_open_min: float = 0
    window_close_min: float = _DAY_MINUTES
    duration_min: float = Field(default=0, ge=0)

    @field_validator("name", "machine_type_id")
    @classmethod
    def _text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("must not be empty")
        return text


class FuelScenario(BaseModel):
    name: str
    variant: FuelVariant = VRPTW
    depot: FuelDepot | None = None
    depots: list[FuelDepot] = Field(default_factory=list)
    machines: list[FuelMachine]
    machine_types: list[FuelType]
    tanker_types: list[TankerType]
    tanker_type_id: str

    @field_validator("name", "tanker_type_id")
    @classmethod
    def _text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("must not be empty")
        return text


class FuelJobRequest(BaseModel):
    scenario: FuelScenario
    solver: str
    time_budget_s: float = Field(default=10, gt=0, le=300)
    seed: int = Field(default=0, ge=0)


@dataclass
class FuelWork:
    scenario: FuelScenario
    solver: str
    time_budget_s: float
    seed: int


def osrm_base() -> str:
    return os.environ.get("OSRM_BASE_URL", "https://router.project-osrm.org").rstrip("/")


def _scenario_depots(scenario: FuelScenario) -> list[FuelDepot]:
    if scenario.variant == MDVRP:
        return list(scenario.depots)
    if scenario.depot is None:
        raise FuelError("place a depot")
    return [scenario.depot]


def validate_scenario(scenario: FuelScenario) -> FuelScenario:
    """Reject a scenario that cannot become the selected road-network variant."""
    if scenario.variant not in FUEL_VARIANTS:
        raise FuelError(f"unsupported variant {scenario.variant!r}; expected one of {FUEL_VARIANTS}")
    if not scenario.machine_types:
        raise FuelError("define at least one machine type")
    if not scenario.tanker_types:
        raise FuelError("define at least one tanker type")
    if not scenario.machines:
        raise FuelError("place at least one machine")
    if len(scenario.machines) > _MAX_MACHINES:
        raise FuelError(f"a fueling scenario can include at most {_MAX_MACHINES} machines")
    _unique_ids("machine type", [item.id for item in scenario.machine_types])
    _unique_ids("tanker type", [item.id for item in scenario.tanker_types])
    machine_ids = {item.id for item in scenario.machine_types}
    tanker = next((item for item in scenario.tanker_types if item.id == scenario.tanker_type_id), None)
    if tanker is None:
        raise FuelError(f"unknown tanker type {scenario.tanker_type_id!r}")
    depots = _scenario_depots(scenario)
    if scenario.variant == MDVRP and len(depots) < 2:
        raise FuelError("MDVRP requires at least two depots")
    timed = scenario.variant == VRPTW
    for depot in depots:
        _check_point(depot.name, depot.lat, depot.lng)
        if timed:
            _check_window("depot shift", depot.window_open_min, depot.window_close_min)
    for machine in scenario.machines:
        if machine.machine_type_id not in machine_ids:
            raise FuelError(f"machine {machine.name!r} uses an unknown machine type")
        _check_point(machine.name, machine.lat, machine.lng)
        if timed:
            _check_window(
                f"{machine.name} refueling window",
                machine.window_open_min,
                machine.window_close_min,
            )
            if not np.isfinite(machine.duration_min):
                raise FuelError(f"{machine.name} refueling duration must be finite")
            if machine.duration_min > machine.window_close_min - machine.window_open_min:
                raise FuelError(f"{machine.name} refueling duration does not fit in its window")
        if machine.fuel_l > tanker.capacity_l:
            raise FuelError(
                f"{machine.name} fuel demand {machine.fuel_l} L exceeds "
                f"tank capacity {tanker.capacity_l} L"
            )
    return scenario


def ensure_fuel_solver(name: str, variant: str = VRPTW) -> None:
    if variant not in FUEL_VARIANTS:
        raise FuelError(f"unsupported variant {variant!r}; expected one of {FUEL_VARIANTS}")
    if name not in FUEL_SOLVERS:
        raise FuelError(
            f"solver {name!r} does not solve fueling scenarios; expected one of {FUEL_SOLVERS}"
        )
    try:
        solver = get_solver(name)
    except KeyError as exc:
        raise FuelError(str(exc)) from exc
    if variant not in solver.supported_variants:
        raise FuelError(f"solver {name!r} does not support {variant}")


def fuel_catalog(variant: str = VRPTW) -> dict:
    if variant not in FUEL_VARIANTS:
        raise FuelError(f"unsupported variant {variant!r}; expected one of {FUEL_VARIANTS}")
    solvers = []
    for name in FUEL_SOLVERS:
        try:
            solver = get_solver(name)
        except KeyError:
            continue
        if variant not in solver.supported_variants:
            continue
        solvers.append({"name": name, "version": solver.version()})
    return {"solvers": solvers}


def build_fuel_instance(
    scenario: FuelScenario, distance_km: np.ndarray, travel_min: np.ndarray
) -> Instance:
    """Build the road instance. Matrices are authoritative; coordinates are geographic.

    ``travel_min`` is stored only for VRPTW. CVRP and MDVRP keep the distance
    matrix and leave every time field empty.
    """
    scenario = validate_scenario(scenario)
    tanker = next(item for item in scenario.tanker_types if item.id == scenario.tanker_type_id)
    depots = _scenario_depots(scenario)
    nodes = [*depots, *scenario.machines]
    coords = np.asarray([[node.lng, node.lat] for node in nodes], dtype=float)
    demands = np.asarray(
        [0] * len(depots) + [machine.fuel_l for machine in scenario.machines],
        dtype=int,
    )
    common = dict(
        name=scenario.name,
        num_nodes=len(nodes),
        coords=coords,
        demands=demands,
        capacity=int(tanker.capacity_l),
        distance=np.asarray(distance_km, dtype=float),
        depot=0,
    )
    try:
        if scenario.variant == VRPTW:
            depot = depots[0]
            # Latest start is close minus service, so refueling finishes inside the window.
            windows = np.asarray(
                [
                    [float(depot.window_open_min), float(depot.window_close_min)],
                    *[
                        [
                            float(machine.window_open_min),
                            float(machine.window_close_min) - float(machine.duration_min),
                        ]
                        for machine in scenario.machines
                    ],
                ],
                dtype=float,
            )
            service = np.asarray(
                [0.0, *[machine.duration_min for machine in scenario.machines]],
                dtype=float,
            )
            return Instance(
                variant=VRPTW,
                time_windows=windows,
                service_times=service,
                travel_times=np.asarray(travel_min, dtype=float),
                **common,
            )
        if scenario.variant == MDVRP:
            return Instance(variant=MDVRP, depot_indices=tuple(range(len(depots))), **common)
        return Instance(variant=CVRP, **common)
    except ValueError as exc:
        raise FuelError(str(exc)) from exc


def matrices_from_table(payload: dict[str, Any], n: int) -> tuple[np.ndarray, np.ndarray]:
    """Convert an OSRM table body into kilometers and minutes."""
    _require_ok(payload, "OSRM table failed")
    durations = payload.get("durations")
    distances = payload.get("distances")
    if not isinstance(durations, list) or not isinstance(distances, list):
        raise FuelError("OSRM table is missing duration or distance")
    if len(durations) != n or len(distances) != n:
        raise FuelError(f"OSRM table has {len(durations)} rows; expected {n}")
    distance_km = np.zeros((n, n), dtype=float)
    travel_min = np.zeros((n, n), dtype=float)
    for i in range(n):
        row_d = durations[i]
        row_m = distances[i]
        if not isinstance(row_d, list) or not isinstance(row_m, list) or len(row_d) != n or len(row_m) != n:
            raise FuelError("OSRM table has a ragged row")
        for j in range(n):
            if row_d[j] is None or row_m[j] is None:
                raise FuelError(f"no driving route between stops {i} and {j}")
            travel_min[i, j] = float(row_d[j]) / 60.0
            distance_km[i, j] = float(row_m[j]) / 1000.0
    return distance_km, travel_min


def route_geometry(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Return full-resolution GeoJSON and the distinct street names along it.

    A missing line raises. Callers must not replace that failure with a straight
    chord between stops.
    """
    _require_ok(payload, "OSRM returned no street path")
    routes = payload.get("routes")
    if not isinstance(routes, list) or not routes or not isinstance(routes[0], dict):
        raise FuelError("OSRM returned no street path")
    geometry = routes[0].get("geometry")
    if not isinstance(geometry, dict) or geometry.get("type") != "LineString":
        raise FuelError("OSRM returned no street path")
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        raise FuelError("OSRM returned no street path")
    streets: list[str] = []
    seen: set[str] = set()
    legs = routes[0].get("legs") or []
    if isinstance(legs, list):
        for leg in legs:
            if not isinstance(leg, dict):
                continue
            for step in leg.get("steps") or []:
                if not isinstance(step, dict):
                    continue
                name = str(step.get("name") or "").strip()
                if name and name not in seen:
                    seen.add(name)
                    streets.append(name)
    return {"type": "LineString", "coordinates": coordinates}, streets


def route_schedule(
    scenario: FuelScenario, travel_min: np.ndarray, routes: list[list[int]]
) -> dict[str, list[Any]]:
    """Clock each route so refueling starts inside the machine window.

    The tanker leaves the depot late enough to reach the first machine when
    that window opens, when the earliest departure can still meet every later
    window and the return. Waiting that cannot be absorbed at the depot stays
    on site. ``arrivals_min`` is the start of refueling, after that wait.
    ``leaves_min`` is when refueling ends and the tanker drives on.
    """
    depart_min: list[float] = []
    arrivals_min: list[list[float]] = []
    leaves_min: list[list[float]] = []
    return_min: list[float] = []
    depot = scenario.depot
    if depot is None:
        raise FuelError("place a depot")
    opens = [float(depot.window_open_min)]
    opens.extend(float(machine.window_open_min) for machine in scenario.machines)
    closes = [float(depot.window_close_min)]
    closes.extend(float(machine.window_close_min) for machine in scenario.machines)
    service = [0.0]
    service.extend(float(machine.duration_min) for machine in scenario.machines)
    for route in routes:
        if not route:
            depart_min.append(opens[0])
            arrivals_min.append([])
            leaves_min.append([])
            return_min.append(opens[0])
            continue
        _replay(opens[0], route, travel_min, opens, closes, service)
        target = opens[route[0]] - float(travel_min[0, route[0]])
        depart = max(opens[0], target)
        arrivals, leaves, back = _replay(depart, route, travel_min, opens, closes, service)
        depart_min.append(depart)
        arrivals_min.append(arrivals)
        leaves_min.append(leaves)
        return_min.append(back)
    return {
        "depart_min": depart_min,
        "arrivals_min": arrivals_min,
        "leaves_min": leaves_min,
        "return_min": return_min,
    }


def _misses_window(violations: list[str]) -> bool:
    markers = ("arrival", "latest", "return", "depot close")
    return any(any(marker in item for marker in markers) for item in violations)


def _replay(
    depart: float,
    route: list[int],
    travel_min: np.ndarray,
    opens: list[float],
    closes: list[float],
    service: list[float],
) -> tuple[list[float], list[float], float]:
    """Return service starts, service ends, and the depot return time."""
    clock = float(depart)
    prev = 0
    arrivals: list[float] = []
    leaves: list[float] = []
    for node in route:
        clock += float(travel_min[prev, node])
        latest = closes[node] - service[node]
        start = max(clock, opens[node])
        if start > latest + _CLOCK_EPS:
            raise FuelError(_WINDOW_ERROR)
        arrivals.append(start)
        clock = start + service[node]
        leaves.append(clock)
        prev = node
    clock += float(travel_min[prev, 0])
    if clock > closes[0] + _CLOCK_EPS:
        raise FuelError(_WINDOW_ERROR)
    return arrivals, leaves, clock


def route_distances(
    distance_km: np.ndarray,
    routes: list[list[int]],
    route_depots: list[int] | None = None,
) -> dict[str, list[Any]]:
    """Driving kilometers for each hop, including the return to that route's depot."""
    homes = list(route_depots or [])
    leg_km: list[list[float]] = []
    route_km: list[float] = []
    for index, route in enumerate(routes):
        home = homes[index] if index < len(homes) else 0
        if not route:
            leg_km.append([])
            route_km.append(0.0)
            continue
        prev = home
        hops: list[float] = []
        for node in route:
            hops.append(float(distance_km[prev, node]))
            prev = node
        hops.append(float(distance_km[prev, home]))
        leg_km.append(hops)
        route_km.append(float(sum(hops)))
    return {"leg_km": leg_km, "route_km": route_km}


def solve_fuel_job(work: FuelWork) -> dict[str, Any]:
    """Fetch the driving matrix, solve, then attach one street path per route."""
    scenario = validate_scenario(work.scenario)
    depots = _scenario_depots(scenario)
    points = [(depot.lng, depot.lat) for depot in depots]
    points.extend((machine.lng, machine.lat) for machine in scenario.machines)
    distance_km, travel_min = matrices_from_table(fetch_table(points), len(points))
    # CVRP and MDVRP scale distance by 1, so the matrix is stored in meters and
    # the reported objective is converted back to kilometers. VRPTW already
    # splits kilometers and minutes inside the solver.
    timed = scenario.variant == VRPTW
    instance_distance = distance_km if timed else distance_km * _METERS_PER_KM
    instance = build_fuel_instance(scenario, instance_distance, travel_min)
    scale_out = 1.0 if timed else _METERS_PER_KM
    solver = get_solver(work.solver)
    try:
        solution = solver.solve(
            instance,
            time_budget_s=work.time_budget_s,
            seed=work.seed,
        )
    except SolverError as exc:
        raise FuelError(str(exc)) from exc
    checked = evaluate.verify(instance, solution)
    if not checked.feasible:
        if timed and _misses_window(checked.violations):
            raise FuelError(_WINDOW_ERROR)
        raise FuelError("; ".join(checked.violations))
    if timed:
        schedule = route_schedule(scenario, travel_min, solution.routes)
    else:
        schedule = {
            "depart_min": [],
            "arrivals_min": [],
            "leaves_min": [],
            "return_min": [],
        }
    route_depots = list(solution.route_depots) if scenario.variant == MDVRP else []
    distances = route_distances(distance_km, solution.routes, route_depots)
    paths = []
    for index, route in enumerate(solution.routes):
        if not route:
            continue
        home = route_depots[index] if index < len(route_depots) else 0
        ordered = [points[home], *[points[node] for node in route], points[home]]
        try:
            geometry, streets = route_geometry(fetch_route(ordered))
        except FuelError as exc:
            raise FuelError(f"route {index + 1}: {exc}") from exc
        paths.append({"stops": list(route), "geometry": geometry, "streets": streets})
    return {
        "routes": solution.routes,
        "route_depots": route_depots,
        "objective": checked.objective / scale_out,
        "solver_objective": solution.objective / scale_out,
        "num_vehicles": checked.num_vehicles,
        "runtime_s": solution.runtime_s,
        "obj_mismatch": checked.obj_mismatch / scale_out,
        "feasible": checked.feasible,
        "violations": list(checked.violations),
        "solver_version": solver.version(),
        "paths": paths,
        **schedule,
        **distances,
    }


_NOMINATIM = "https://nominatim.openstreetmap.org/search"
_MAX_ADDRESS_QUERY = 200


def search_places(query: str) -> list[dict[str, Any]]:
    """Resolve a written address to at most five map places."""
    text = " ".join(query.split())
    if not text:
        raise FuelError("address query must not be empty")
    if len(text) > _MAX_ADDRESS_QUERY:
        raise FuelError("address query is too long")
    url = _NOMINATIM + "?" + urllib.parse.urlencode(
        {
            "q": text,
            "format": "jsonv2",
            "limit": "5",
            "accept-language": "fa",
        }
    )
    places: list[dict[str, Any]] = []
    for item in _get_nominatim(url)[:5]:
        place = _place_from_nominatim(item)
        if place is not None:
            places.append(place)
    return places


def fetch_table(points: list[tuple[float, float]]) -> dict[str, Any]:
    url = (
        f"{osrm_base()}/table/v1/driving/{_coord_path(points)}"
        "?annotations=duration,distance"
    )
    return _get_json(url)


def fetch_route(points: list[tuple[float, float]]) -> dict[str, Any]:
    url = (
        f"{osrm_base()}/route/v1/driving/{_coord_path(points)}"
        "?overview=full&geometries=geojson&steps=true"
    )
    return _get_json(url)


def _get_nominatim(url: str) -> list[Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "vrpbench-fueling"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raise FuelError(f"address lookup failed: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise FuelError(f"address lookup failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise FuelError("address lookup failed: response is not JSON") from exc
    if not isinstance(payload, list):
        raise FuelError("address lookup failed: response is not a list")
    return payload


def _place_from_nominatim(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    label = item.get("display_name")
    if not isinstance(label, str) or not label.strip():
        return None
    try:
        lat = float(item["lat"])
        lng = float(item["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    bounds = _place_bounds(item.get("boundingbox"), lat, lng)
    if bounds is None:
        return None
    south, north, west, east = bounds
    return {
        "label": label.strip(),
        "lat": lat,
        "lng": lng,
        "south": south,
        "north": north,
        "west": west,
        "east": east,
    }


def _place_bounds(
    raw: Any, lat: float, lng: float
) -> tuple[float, float, float, float] | None:
    if raw is None:
        return (lat, lat, lng, lng)
    if not isinstance(raw, list) or len(raw) != 4:
        return None
    try:
        south, north, west, east = (float(part) for part in raw)
    except (TypeError, ValueError):
        return None
    if south > north:
        south, north = north, south
    if west > east:
        west, east = east, west
    if not (-90 <= south <= north <= 90 and -180 <= west <= east <= 180):
        return None
    return (south, north, west, east)


def _get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "vrpbench-fueling"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raise FuelError(f"OSRM request failed: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise FuelError(f"OSRM request failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise FuelError("OSRM returned a response that is not JSON") from exc
    if not isinstance(payload, dict):
        raise FuelError("OSRM returned a response that is not an object")
    return payload


def _coord_path(points: list[tuple[float, float]]) -> str:
    raw = ";".join(f"{lng:.6f},{lat:.6f}" for lng, lat in points)
    return urllib.parse.quote(raw, safe=";,.")


def _require_ok(payload: dict[str, Any], fallback: str) -> None:
    if payload.get("code") == "Ok":
        return
    message = payload.get("message")
    raise FuelError(str(message) if message else fallback)


def _unique_ids(label: str, ids: list[str]) -> None:
    if len(ids) != len(set(ids)):
        raise FuelError(f"each {label} needs its own id")


def _check_point(label: str, lat: float, lng: float) -> None:
    if not np.isfinite(lat) or not np.isfinite(lng):
        raise FuelError(f"{label} coordinates must be finite")
    if not -90 <= lat <= 90 or not -180 <= lng <= 180:
        raise FuelError(f"{label} coordinates are outside the map")


def _check_window(label: str, open_min: float, close_min: float) -> None:
    if not np.isfinite(open_min) or not np.isfinite(close_min):
        raise FuelError(f"{label} must be finite")
    if not (0 <= open_min <= close_min <= _DAY_MINUTES):
        raise FuelError(f"{label} must fall within a single day")
