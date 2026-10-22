"""Scenario JSON and conversion into a benchmark :class:`Instance`.

The studio accepts CVRP, VRPTW, and MDVRP. Distances follow the loaders:
nearest-integer Euclidean for CVRP and MDVRP, raw Euclidean for VRPTW.
"""

import math
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, Field, field_validator

from vrpbench.core.instance import CVRP, MDVRP, VRPTW, Instance

STUDIO_VARIANTS = (CVRP, VRPTW, MDVRP)
DistanceKind = Literal["euclidean_rint", "euclidean_float"]


class ScenarioError(ValueError):
    """A scenario cannot be turned into an instance."""


class GeoPoint(BaseModel):
    lat: float
    lng: float


class ScenarioNode(BaseModel):
    role: Literal["depot", "customer"]
    x: float
    y: float
    demand: int = 0
    ready: float | None = None
    due: float | None = None
    service: float | None = None
    geo: GeoPoint | None = None

    @field_validator("x", "y")
    @classmethod
    def _finite_coord(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("coordinates must be finite")
        return float(value)

    @field_validator("demand")
    @classmethod
    def _non_negative_demand(cls, value: int) -> int:
        if value < 0:
            raise ValueError("demand must be non-negative")
        return int(value)


class Scenario(BaseModel):
    name: str = "scenario"
    variant: str
    capacity: int = Field(ge=1)
    nodes: list[ScenarioNode]

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("name must not be empty")
        return text

    @field_validator("variant")
    @classmethod
    def _variant(cls, value: str) -> str:
        if value not in STUDIO_VARIANTS:
            raise ValueError(
                f"unsupported variant {value!r}; expected one of {STUDIO_VARIANTS}"
            )
        return value


class ScenarioPreview(BaseModel):
    ok: bool = True
    scenario: Scenario
    num_depots: int
    num_customers: int
    distance_kind: DistanceKind


def distance_kind(variant: str) -> DistanceKind:
    if variant == VRPTW:
        return "euclidean_float"
    return "euclidean_rint"


def canonicalize(scenario: Scenario) -> Scenario:
    """Place every depot before every customer, preserving relative order."""
    depots = [node for node in scenario.nodes if node.role == "depot"]
    customers = [node for node in scenario.nodes if node.role == "customer"]
    return scenario.model_copy(update={"nodes": depots + customers})


def build_instance(scenario: Scenario) -> Instance:
    """Validate a scenario and build the authoritative instance."""
    scenario = canonicalize(scenario)
    _validate_roles(scenario)
    coords = np.asarray([[node.x, node.y] for node in scenario.nodes], dtype=float)
    demands = np.asarray([_node_demand(node) for node in scenario.nodes], dtype=int)
    distance = _distance_matrix(coords, scenario.variant)
    depots = [node for node in scenario.nodes if node.role == "depot"]
    time_windows = service_times = None
    depot_indices = None
    if scenario.variant == VRPTW:
        time_windows, service_times = _time_fields(scenario)
    if scenario.variant == MDVRP:
        depot_indices = tuple(range(len(depots)))
    try:
        return Instance(
            name=scenario.name,
            variant=scenario.variant,
            num_nodes=len(scenario.nodes),
            coords=coords,
            demands=demands,
            capacity=int(scenario.capacity),
            distance=distance,
            depot=0,
            depot_indices=depot_indices,
            num_vehicles=None,
            time_windows=time_windows,
            service_times=service_times,
        )
    except ValueError as exc:
        raise ScenarioError(str(exc)) from exc


def preview_from_scenario(scenario: Scenario) -> ScenarioPreview:
    canonical = canonicalize(scenario)
    build_instance(canonical)
    depots = sum(1 for node in canonical.nodes if node.role == "depot")
    return ScenarioPreview(
        scenario=canonical,
        num_depots=depots,
        num_customers=len(canonical.nodes) - depots,
        distance_kind=distance_kind(canonical.variant),
    )


def preview_from_instance(instance: Instance) -> ScenarioPreview:
    if instance.variant not in STUDIO_VARIANTS:
        raise ScenarioError(
            f"unsupported variant {instance.variant!r}; expected one of {STUDIO_VARIANTS}"
        )
    depot_ids = set(instance.depot_indices) if instance.depot_indices else {instance.depot}
    nodes: list[ScenarioNode] = []
    for index in range(instance.num_nodes):
        ready = due = service = None
        if instance.time_windows is not None and instance.service_times is not None:
            ready = float(instance.time_windows[index, 0])
            due = float(instance.time_windows[index, 1])
            service = float(instance.service_times[index])
        nodes.append(
            ScenarioNode(
                role="depot" if index in depot_ids else "customer",
                x=float(instance.coords[index, 0]),
                y=float(instance.coords[index, 1]),
                demand=int(instance.demands[index]),
                ready=ready,
                due=due,
                service=service,
            )
        )
    return preview_from_scenario(
        Scenario(
            name=instance.name,
            variant=instance.variant,
            capacity=int(instance.capacity),
            nodes=nodes,
        )
    )


def _validate_roles(scenario: Scenario) -> None:
    depots = [node for node in scenario.nodes if node.role == "depot"]
    customers = [node for node in scenario.nodes if node.role == "customer"]
    if scenario.variant == MDVRP:
        if len(depots) < 2:
            raise ScenarioError("MDVRP requires at least two depots")
    elif len(depots) != 1:
        raise ScenarioError(f"{scenario.variant} requires exactly one depot")
    if not customers:
        raise ScenarioError("scenario requires at least one customer")
    for node in customers:
        if node.demand > scenario.capacity:
            raise ScenarioError(
                f"customer demand {node.demand} exceeds capacity {scenario.capacity}"
            )


def _node_demand(node: ScenarioNode) -> int:
    if node.role == "depot" and node.demand != 0:
        raise ScenarioError("depot demand must be 0")
    return 0 if node.role == "depot" else int(node.demand)


def _time_fields(scenario: Scenario) -> tuple[np.ndarray, np.ndarray]:
    windows: list[list[float]] = []
    service: list[float] = []
    for node in scenario.nodes:
        if node.ready is None or node.due is None or node.service is None:
            raise ScenarioError("VRPTW requires ready, due, and service on every node")
        if not all(math.isfinite(value) for value in (node.ready, node.due, node.service)):
            raise ScenarioError("VRPTW time fields must be finite")
        if node.service < 0:
            raise ScenarioError("service time must be non-negative")
        if node.ready > node.due:
            raise ScenarioError("ready time must be at or before the due time")
        windows.append([float(node.ready), float(node.due)])
        service.append(float(node.service))
    return np.asarray(windows, dtype=float), np.asarray(service, dtype=float)


def _distance_matrix(coords: np.ndarray, variant: str) -> np.ndarray:
    diff = coords[:, None, :] - coords[None, :, :]
    euclid = np.sqrt((diff**2).sum(axis=2))
    if variant == VRPTW:
        return euclid
    return np.rint(euclid)


def format_validation_error(exc: Exception) -> str:
    """Flatten a pydantic validation error into one readable sentence."""
    if hasattr(exc, "errors"):
        parts: list[str] = []
        for item in exc.errors():  # type: ignore[attr-defined]
            loc = ".".join(str(part) for part in item.get("loc", ()))
            message = item.get("msg", "invalid value")
            parts.append(f"{loc}: {message}" if loc else str(message))
        if parts:
            return "; ".join(parts)
    return str(exc)


def scenario_from_payload(payload: dict[str, Any]) -> Scenario:
    try:
        return Scenario.model_validate(payload)
    except Exception as exc:
        raise ScenarioError(format_validation_error(exc)) from exc
