"""Fueling scenarios: a single-depot VRPTW solved on driving roads.

Machines need an integer number of liters inside a refueling window. One tanker
type supplies the tank capacity. OpenStreetMap driving distances (kilometers)
are the objective; driving durations (minutes) enforce the windows. Solved
routes are drawn from OSRM's full road geometry, never from straight chords.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

import numpy as np
from pydantic import BaseModel, Field, field_validator

from vrpbench.core import evaluate
from vrpbench.core.instance import VRPTW, Instance
from vrpbench.solvers import get_solver
from vrpbench.solvers.base import SolverError

FUEL_SOLVERS = ("pyvrp", "ortools")
_MAX_MACHINES = 99
_DAY_MINUTES = 24 * 60


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
    window_open_min: float
    window_close_min: float

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
    window_open_min: float
    window_close_min: float
    duration_min: float = Field(ge=0)

    @field_validator("name", "machine_type_id")
    @classmethod
    def _text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("must not be empty")
        return text


class FuelScenario(BaseModel):
    name: str
    depot: FuelDepot
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


def validate_scenario(scenario: FuelScenario) -> FuelScenario:
    """Reject a scenario that cannot become a single-depot VRPTW."""
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
    _check_point("depot", scenario.depot.lat, scenario.depot.lng)
    _check_window("depot shift", scenario.depot.window_open_min, scenario.depot.window_close_min)
    for machine in scenario.machines:
        if machine.machine_type_id not in machine_ids:
            raise FuelError(f"machine {machine.name!r} uses an unknown machine type")
        _check_point(machine.name, machine.lat, machine.lng)
        _check_window(
            f"{machine.name} refueling window",
            machine.window_open_min,
            machine.window_close_min,
        )
        if not np.isfinite(machine.duration_min):
            raise FuelError(f"{machine.name} refueling duration must be finite")
        if machine.fuel_l > tanker.capacity_l:
            raise FuelError(
                f"{machine.name} fuel demand {machine.fuel_l} L exceeds "
                f"tank capacity {tanker.capacity_l} L"
            )
    return scenario


def ensure_fuel_solver(name: str) -> None:
    if name not in FUEL_SOLVERS:
        raise FuelError(
            f"solver {name!r} does not solve fueling scenarios; expected one of {FUEL_SOLVERS}"
        )
    try:
        solver = get_solver(name)
    except KeyError as exc:
        raise FuelError(str(exc)) from exc
    if VRPTW not in solver.supported_variants:
        raise FuelError(f"solver {name!r} does not support VRPTW")


def fuel_catalog() -> dict:
    solvers = []
    for name in FUEL_SOLVERS:
        try:
            solver = get_solver(name)
        except KeyError:
            continue
        if VRPTW not in solver.supported_variants:
            continue
        solvers.append({"name": name, "version": solver.version()})
    return {"solvers": solvers}


def build_fuel_instance(
    scenario: FuelScenario, distance_km: np.ndarray, travel_min: np.ndarray
) -> Instance:
    """Build the VRPTW instance. Matrices are authoritative; coordinates are geographic."""
    scenario = validate_scenario(scenario)
    tanker = next(item for item in scenario.tanker_types if item.id == scenario.tanker_type_id)
    nodes = [scenario.depot, *scenario.machines]
    coords = np.asarray([[node.lng, node.lat] for node in nodes], dtype=float)
    demands = np.asarray([0, *[machine.fuel_l for machine in scenario.machines]], dtype=int)
    windows = np.asarray(
        [[node.window_open_min, node.window_close_min] for node in nodes],
        dtype=float,
    )
    service = np.asarray(
        [0.0, *[machine.duration_min for machine in scenario.machines]],
        dtype=float,
    )
    try:
        return Instance(
            name=scenario.name,
            variant=VRPTW,
            num_nodes=len(nodes),
            coords=coords,
            demands=demands,
            capacity=int(tanker.capacity_l),
            distance=np.asarray(distance_km, dtype=float),
            time_windows=windows,
            service_times=service,
            travel_times=np.asarray(travel_min, dtype=float),
        )
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
    """Clock each route the same way the time-window check does.

    The tanker leaves the depot when the shift opens. ``arrivals_min`` is the
    moment it reaches each machine, before waiting for that window.
    ``leaves_min`` is when it drives on, after that wait and the refueling.
    It then drives back to the depot.
    """
    depart_min: list[float] = []
    arrivals_min: list[list[float]] = []
    leaves_min: list[list[float]] = []
    return_min: list[float] = []
    opens = [float(scenario.depot.window_open_min)]
    opens.extend(float(machine.window_open_min) for machine in scenario.machines)
    service = [0.0]
    service.extend(float(machine.duration_min) for machine in scenario.machines)
    for route in routes:
        clock = opens[0]
        depart_min.append(clock)
        if not route:
            arrivals_min.append([])
            leaves_min.append([])
            return_min.append(clock)
            continue
        prev = 0
        arrivals: list[float] = []
        leaves: list[float] = []
        for node in route:
            clock += float(travel_min[prev, node])
            arrivals.append(clock)
            clock = max(clock, opens[node])
            clock += service[node]
            leaves.append(clock)
            prev = node
        clock += float(travel_min[prev, 0])
        arrivals_min.append(arrivals)
        leaves_min.append(leaves)
        return_min.append(clock)
    return {
        "depart_min": depart_min,
        "arrivals_min": arrivals_min,
        "leaves_min": leaves_min,
        "return_min": return_min,
    }


def route_distances(distance_km: np.ndarray, routes: list[list[int]]) -> dict[str, list[Any]]:
    """Driving kilometers for each hop, including the return to the depot."""
    leg_km: list[list[float]] = []
    route_km: list[float] = []
    for route in routes:
        if not route:
            leg_km.append([])
            route_km.append(0.0)
            continue
        prev = 0
        hops: list[float] = []
        for node in route:
            hops.append(float(distance_km[prev, node]))
            prev = node
        hops.append(float(distance_km[prev, 0]))
        leg_km.append(hops)
        route_km.append(float(sum(hops)))
    return {"leg_km": leg_km, "route_km": route_km}


def solve_fuel_job(work: FuelWork) -> dict[str, Any]:
    """Fetch the driving matrix, solve, then attach one street path per route."""
    scenario = validate_scenario(work.scenario)
    points = [(scenario.depot.lng, scenario.depot.lat)]
    points.extend((machine.lng, machine.lat) for machine in scenario.machines)
    distance_km, travel_min = matrices_from_table(fetch_table(points), len(points))
    instance = build_fuel_instance(scenario, distance_km, travel_min)
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
    paths = []
    for index, route in enumerate(solution.routes):
        if not route:
            continue
        ordered = [points[0], *[points[node] for node in route], points[0]]
        try:
            geometry, streets = route_geometry(fetch_route(ordered))
        except FuelError as exc:
            raise FuelError(f"route {index + 1}: {exc}") from exc
        paths.append({"stops": list(route), "geometry": geometry, "streets": streets})
    schedule = route_schedule(scenario, travel_min, solution.routes)
    distances = route_distances(distance_km, solution.routes)
    return {
        "routes": solution.routes,
        "route_depots": [],
        "objective": checked.objective,
        "solver_objective": solution.objective,
        "num_vehicles": checked.num_vehicles,
        "runtime_s": solution.runtime_s,
        "obj_mismatch": checked.obj_mismatch,
        "feasible": checked.feasible,
        "violations": list(checked.violations),
        "solver_version": solver.version(),
        "paths": paths,
        **schedule,
        **distances,
    }


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
