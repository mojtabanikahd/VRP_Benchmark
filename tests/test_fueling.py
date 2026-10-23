"""Fueling scenarios, road travel times, and street geometry."""

from __future__ import annotations

import time
from dataclasses import replace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from vrpbench.core import evaluate
from vrpbench.core.instance import Instance
from vrpbench.core.solution import Solution
from vrpbench.solvers.road_time import ROAD_DISTANCE_SCALE, ROAD_TIME_SCALE, scaled_vrptw
from web.api.fueling import (
    FuelError,
    FuelScenario,
    build_fuel_instance,
    matrices_from_table,
    route_geometry,
    route_schedule,
)
from web.api.main import app

client = TestClient(app)

STREET = {
    "type": "LineString",
    "coordinates": [[-0.12, 51.5], [-0.12, 51.51], [-0.11, 51.52], [-0.10, 51.52]],
}


def _scenario(**overrides) -> dict:
    payload = {
        "name": "yard",
        "depot": {
            "name": "Depot",
            "lat": 51.5,
            "lng": -0.12,
            "window_open_min": 360,
            "window_close_min": 1320,
        },
        "machines": [
            {
                "name": "Excavator",
                "machine_type_id": "mt",
                "lat": 51.52,
                "lng": -0.10,
                "fuel_l": 40,
                "window_open_min": 480,
                "window_close_min": 960,
                "duration_min": 15,
            }
        ],
        "machine_types": [{"id": "mt", "name": "Excavator"}],
        "tanker_types": [{"id": "tt", "name": "Tanker", "capacity_l": 200}],
        "tanker_type_id": "tt",
    }
    payload.update(overrides)
    return payload


def _table() -> dict:
    return {
        "code": "Ok",
        "durations": [[0, 600], [600, 0]],
        "distances": [[0, 2000], [2000, 0]],
    }


def _route() -> dict:
    return {
        "code": "Ok",
        "routes": [
            {
                "geometry": STREET,
                "legs": [
                    {"steps": [{"name": "High Street"}, {"name": ""}, {"name": "High Street"}, {"name": "Yard Road"}]},
                    {"steps": [{"name": "Yard Road"}, {"name": "Mill Lane"}]},
                ],
            }
        ],
    }


def test_route_schedule_records_arrival_before_the_window_wait():
    scenario = FuelScenario.model_validate(_scenario())
    travel = np.zeros((2, 2))
    travel[0, 1] = travel[1, 0] = 10
    clock = route_schedule(scenario, travel, [[1]])
    assert clock["depart_min"] == pytest.approx([360])
    assert clock["arrivals_min"][0] == pytest.approx([370])
    # The machine window opens at 08:00, so refueling ends at 08:15.
    assert clock["leaves_min"][0] == pytest.approx([495])
    assert clock["return_min"] == pytest.approx([505])


def test_route_schedule_services_immediately_when_the_window_is_open():
    payload = _scenario()
    payload["machines"][0]["window_open_min"] = 360
    scenario = FuelScenario.model_validate(payload)
    travel = np.zeros((2, 2))
    travel[0, 1] = travel[1, 0] = 10
    clock = route_schedule(scenario, travel, [[1]])
    assert clock["arrivals_min"][0] == pytest.approx([370])
    # 06:10 arrival, 15 minutes of service, then 10 minutes back to the depot.
    assert clock["leaves_min"][0] == pytest.approx([385])
    assert clock["return_min"] == pytest.approx([395])


def test_travel_times_flag_a_late_arrival_distance_would_allow(vrptw_instance: Instance):
    # Each customer on its own route is on time when travel equals distance.
    # Stretching only the drive to customer 3 makes that same plan late.
    direct = Solution(routes=[[1], [2], [3]], objective=0.0, feasible=True, runtime_s=0.0)
    assert evaluate.verify(vrptw_instance, direct).feasible, evaluate.verify(vrptw_instance, direct).violations
    slow = np.array(vrptw_instance.distance, copy=True)
    slow[0, 3] = 100.0
    road = replace(vrptw_instance, travel_times=slow)
    checked = evaluate.verify(road, direct)
    assert not checked.feasible
    assert any("latest" in item for item in checked.violations)
    assert evaluate.total_distance(road, direct) == pytest.approx(
        evaluate.total_distance(vrptw_instance, direct)
    )


def test_travel_times_rejected_outside_vrptw(cvrp_instance: Instance):
    with pytest.raises(ValueError, match="only valid for VRPTW"):
        replace(cvrp_instance, travel_times=np.zeros((4, 4)))


def test_scaled_vrptw_keeps_solomon_scale(vrptw_instance: Instance):
    distance, duration, distance_scale, time_scale = scaled_vrptw(vrptw_instance, 10)
    assert distance_scale == 10
    assert time_scale == 10
    assert np.array_equal(distance, duration)


def test_scaled_vrptw_splits_kilometers_and_minutes(vrptw_instance: Instance):
    distance_km = np.full((4, 4), 1.5)
    np.fill_diagonal(distance_km, 0.0)
    minutes = np.full((4, 4), 2.5)
    np.fill_diagonal(minutes, 0.0)
    road = replace(vrptw_instance, distance=distance_km, travel_times=minutes)
    distance, duration, distance_scale, time_scale = scaled_vrptw(road, 10)
    assert distance_scale == ROAD_DISTANCE_SCALE
    assert time_scale == ROAD_TIME_SCALE
    assert distance[0, 1] == 1500
    assert duration[0, 1] == 25


def test_pyvrp_duration_matrix_uses_minutes_not_kilometers(vrptw_instance: Instance):
    pyvrp = pytest.importorskip("pyvrp")
    from vrpbench.solvers.pyvrp_solver import _build_data

    distance_km = np.full((4, 4), 1.5)
    np.fill_diagonal(distance_km, 0.0)
    minutes = np.full((4, 4), 2.5)
    np.fill_diagonal(minutes, 0.0)
    road = replace(vrptw_instance, distance=distance_km, travel_times=minutes)
    data = _build_data(pyvrp, road, 10)
    assert int(np.asarray(data.distance_matrix(0))[0, 1]) == 1500
    assert int(np.asarray(data.duration_matrix(0))[0, 1]) == 25
    assert int(data.clients()[0].tw_early) == int(round(float(road.time_windows[1, 0]) * ROAD_TIME_SCALE))


def test_matrices_from_table_convert_units():
    distance_km, travel_min = matrices_from_table(_table(), 2)
    assert distance_km[0, 1] == pytest.approx(2.0)
    assert travel_min[0, 1] == pytest.approx(10.0)


def test_build_fuel_instance_is_single_depot_vrptw():
    distance_km, travel_min = matrices_from_table(_table(), 2)
    instance = build_fuel_instance(FuelScenario.model_validate(_scenario()), distance_km, travel_min)
    assert instance.variant == "VRPTW"
    assert instance.depot == 0
    assert list(instance.customers) == [1]
    assert int(instance.demands[1]) == 40
    assert instance.capacity == 200
    assert instance.time_windows[1].tolist() == [480.0, 960.0]
    assert instance.service_times[1] == pytest.approx(15.0)
    assert instance.distance[0, 1] == pytest.approx(2.0)
    assert instance.travel_times is not None
    assert instance.travel_times[0, 1] == pytest.approx(10.0)


def test_route_geometry_keeps_the_street_line_and_names():
    geometry, streets = route_geometry(_route())
    assert geometry == STREET
    assert streets == ["High Street", "Yard Road", "Mill Lane"]


def test_missing_route_geometry_raises_instead_of_a_straight_line():
    with pytest.raises(FuelError, match="no street path"):
        route_geometry({"code": "Ok", "routes": [{"geometry": None, "legs": []}]})


def test_fuel_demand_above_tank_capacity_is_rejected():
    payload = _scenario()
    payload["machines"][0]["fuel_l"] = 500
    response = client.post(
        "/api/fueling/jobs",
        json={"scenario": payload, "solver": "pyvrp", "time_budget_s": 2, "seed": 0},
    )
    assert response.status_code == 422
    assert "tank capacity" in response.text


def test_fuel_catalog_lists_pyvrp_and_ortools_only():
    response = client.get("/api/fueling/catalog")
    assert response.status_code == 200
    names = {item["name"] for item in response.json()["solvers"]}
    assert names == {"pyvrp", "ortools"}


def test_fuel_job_returns_the_osrm_street_path(monkeypatch: pytest.MonkeyPatch):
    def fake_get(url: str) -> dict:
        if "/table/" in url:
            return _table()
        if "/route/" in url:
            return _route()
        raise AssertionError(url)

    monkeypatch.setattr("web.api.fueling._get_json", fake_get)
    created = client.post(
        "/api/fueling/jobs",
        json={"scenario": _scenario(), "solver": "pyvrp", "time_budget_s": 2, "seed": 0},
    )
    assert created.status_code == 200, created.text
    record = _wait(created.json()["id"])
    assert record["status"] == "ok", record
    result = record["result"]
    assert result["feasible"] is True
    assert result["objective"] == pytest.approx(4.0, abs=1e-2)
    assert result["obj_mismatch"] == pytest.approx(0.0, abs=1e-2)
    assert result["paths"][0]["geometry"] == STREET
    assert result["paths"][0]["streets"] == ["High Street", "Yard Road", "Mill Lane"]
    assert result["paths"][0]["stops"] == result["routes"][0]
    assert result["depart_min"][0] == pytest.approx(360)
    assert result["arrivals_min"][0][0] == pytest.approx(370)
    assert result["leaves_min"][0][0] == pytest.approx(495)
    assert result["return_min"][0] == pytest.approx(505)
    assert result["leg_km"][0] == pytest.approx([2.0, 2.0])
    assert result["route_km"][0] == pytest.approx(4.0)


def test_fuel_job_fails_when_the_street_path_is_missing(monkeypatch: pytest.MonkeyPatch):
    def fake_get(url: str) -> dict:
        if "/table/" in url:
            return _table()
        return {"code": "Ok", "routes": [{"geometry": {"type": "LineString", "coordinates": []}}]}

    monkeypatch.setattr("web.api.fueling._get_json", fake_get)
    created = client.post(
        "/api/fueling/jobs",
        json={"scenario": _scenario(), "solver": "ortools", "time_budget_s": 2, "seed": 0},
    )
    assert created.status_code == 200, created.text
    record = _wait(created.json()["id"])
    assert record["status"] == "error"
    assert record["result"] is None
    assert "street path" in record["error"]


def _wait(job_id: str) -> dict:
    deadline = time.time() + 30
    record = None
    while time.time() < deadline:
        record = client.get(f"/api/jobs/{job_id}").json()
        if record["status"] in {"ok", "error"}:
            return record
        time.sleep(0.2)
    assert record is not None
    return record
