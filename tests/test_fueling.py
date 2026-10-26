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
    route_distances,
    route_geometry,
    route_schedule,
    search_places,
    validate_scenario,
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


def test_route_schedule_delays_departure_until_the_window_opens():
    scenario = FuelScenario.model_validate(_scenario())
    travel = np.zeros((2, 2))
    travel[0, 1] = travel[1, 0] = 10
    clock = route_schedule(scenario, travel, [[1]])
    # Leave at 07:50 so refueling starts at 08:00, not at the 06:10 raw arrival.
    assert clock["depart_min"] == pytest.approx([470])
    assert clock["arrivals_min"][0] == pytest.approx([480])
    assert clock["leaves_min"][0] == pytest.approx([495])
    assert clock["return_min"] == pytest.approx([505])


def test_route_schedule_meets_an_afternoon_window_by_leaving_later():
    payload = _scenario()
    payload["machines"][0]["window_open_min"] = 15 * 60
    payload["machines"][0]["window_close_min"] = 16 * 60
    payload["machines"][0]["duration_min"] = 15
    scenario = FuelScenario.model_validate(payload)
    travel = np.zeros((2, 2))
    travel[0, 1] = travel[1, 0] = 30
    clock = route_schedule(scenario, travel, [[1]])
    assert clock["depart_min"] == pytest.approx([15 * 60 - 30])
    assert clock["arrivals_min"][0] == pytest.approx([15 * 60])
    assert clock["leaves_min"][0] == pytest.approx([15 * 60 + 15])
    assert clock["return_min"] == pytest.approx([15 * 60 + 45])


def test_route_schedule_reports_service_start_when_a_later_stop_is_early():
    payload = _scenario()
    second = dict(payload["machines"][0])
    second["name"] = "Second"
    second["lat"] = 51.53
    second["window_open_min"] = 8 * 60 + 30
    second["duration_min"] = 10
    payload["machines"].append(second)
    scenario = FuelScenario.model_validate(payload)
    travel = np.zeros((3, 3))
    travel[0, 1] = travel[1, 0] = 10
    travel[1, 2] = travel[2, 1] = 10
    travel[0, 2] = travel[2, 0] = 20
    clock = route_schedule(scenario, travel, [[1, 2]])
    assert clock["arrivals_min"][0][0] == pytest.approx(8 * 60)
    assert clock["leaves_min"][0][0] == pytest.approx(8 * 60 + 15)
    assert clock["arrivals_min"][0][1] == pytest.approx(8 * 60 + 30)
    assert clock["leaves_min"][0][1] == pytest.approx(8 * 60 + 40)


def test_route_schedule_rejects_a_drive_that_misses_the_window():
    payload = _scenario()
    payload["depot"]["window_open_min"] = 15 * 60
    payload["depot"]["window_close_min"] = 22 * 60
    payload["machines"][0]["window_open_min"] = 15 * 60
    payload["machines"][0]["window_close_min"] = 15 * 60 + 30
    payload["machines"][0]["duration_min"] = 10
    scenario = FuelScenario.model_validate(payload)
    travel = np.zeros((2, 2))
    travel[0, 1] = travel[1, 0] = 120
    with pytest.raises(FuelError, match="refueling windows"):
        route_schedule(scenario, travel, [[1]])


def test_refueling_longer_than_the_window_is_rejected():
    payload = _scenario()
    payload["machines"][0]["window_open_min"] = 15 * 60
    payload["machines"][0]["window_close_min"] = 16 * 60
    payload["machines"][0]["duration_min"] = 90
    with pytest.raises(FuelError, match="does not fit"):
        validate_scenario(FuelScenario.model_validate(payload))


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
    assert instance.time_windows[1].tolist() == [480.0, 945.0]
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


def test_search_places_reads_nominatim_bounds(monkeypatch: pytest.MonkeyPatch):
    def fake_get(url: str) -> list:
        assert "format=jsonv2" in url
        assert "accept-language=fa" in url
        assert "limit=5" in url
        return [
            {
                "display_name": "آزادی، تهران",
                "lat": "35.7",
                "lon": "51.3",
                "boundingbox": ["35.6", "35.8", "51.2", "51.4"],
            },
            {"display_name": "بدون مختصات"},
            {
                "display_name": "نقطه",
                "lat": "32.6",
                "lon": "51.6",
            },
        ]

    monkeypatch.setattr("web.api.fueling._get_nominatim", fake_get)
    assert search_places("  آزادی   تهران ") == [
        {
            "label": "آزادی، تهران",
            "lat": 35.7,
            "lng": 51.3,
            "south": 35.6,
            "north": 35.8,
            "west": 51.2,
            "east": 51.4,
        },
        {
            "label": "نقطه",
            "lat": 32.6,
            "lng": 51.6,
            "south": 32.6,
            "north": 32.6,
            "west": 51.6,
            "east": 51.6,
        },
    ]


def test_search_places_rejects_a_blank_query():
    with pytest.raises(FuelError, match="empty"):
        search_places("   ")


def test_geocode_endpoint_returns_places(monkeypatch: pytest.MonkeyPatch):
    def fake_get(url: str) -> list:
        assert "q=" in url
        return [
            {
                "display_name": "اصفهان",
                "lat": "32.65",
                "lon": "51.67",
                "boundingbox": ["32.5", "32.8", "51.5", "51.8"],
            }
        ]

    monkeypatch.setattr("web.api.fueling._get_nominatim", fake_get)
    response = client.get("/api/fueling/geocode", params={"q": "اصفهان"})
    assert response.status_code == 200
    assert response.json() == {
        "places": [
            {
                "label": "اصفهان",
                "lat": 32.65,
                "lng": 51.67,
                "south": 32.5,
                "north": 32.8,
                "west": 51.5,
                "east": 51.8,
            }
        ]
    }


def test_geocode_endpoint_rejects_a_blank_query():
    response = client.get("/api/fueling/geocode", params={"q": " "})
    assert response.status_code == 422
    assert "empty" in response.text


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
    assert result["depart_min"][0] == pytest.approx(470)
    assert result["arrivals_min"][0][0] == pytest.approx(480)
    assert result["leaves_min"][0][0] == pytest.approx(495)
    assert result["return_min"][0] == pytest.approx(505)
    assert result["leg_km"][0] == pytest.approx([2.0, 2.0])
    assert result["route_km"][0] == pytest.approx(4.0)


def test_fuel_job_rejects_a_window_the_drive_cannot_reach(monkeypatch: pytest.MonkeyPatch):
    def fake_get(url: str) -> dict:
        if "/table/" in url:
            return {
                "code": "Ok",
                "durations": [[0, 120 * 60], [120 * 60, 0]],
                "distances": [[0, 10_000], [10_000, 0]],
            }
        return _route()

    payload = _scenario()
    payload["depot"]["window_open_min"] = 15 * 60
    payload["depot"]["window_close_min"] = 22 * 60
    payload["machines"][0]["window_open_min"] = 15 * 60
    payload["machines"][0]["window_close_min"] = 15 * 60 + 30
    payload["machines"][0]["duration_min"] = 10
    monkeypatch.setattr("web.api.fueling._get_json", fake_get)
    created = client.post(
        "/api/fueling/jobs",
        json={"scenario": payload, "solver": "pyvrp", "time_budget_s": 2, "seed": 0},
    )
    assert created.status_code == 200, created.text
    record = _wait(created.json()["id"])
    assert record["status"] == "error", record
    assert record["result"] is None
    assert "window" in record["error"].lower()


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


def test_build_cvrp_ignores_time_windows():
    payload = _scenario()
    payload["variant"] = "CVRP"
    payload["depot"]["window_open_min"] = 100
    payload["depot"]["window_close_min"] = 10
    distance, travel = matrices_from_table(_table(), 2)
    instance = build_fuel_instance(FuelScenario.model_validate(payload), distance, travel)
    assert instance.variant == "CVRP"
    assert instance.time_windows is None
    assert instance.service_times is None
    assert instance.travel_times is None
    assert instance.depot_indices is None
    assert list(instance.customers) == [1]


def test_mdvrp_requires_two_depots():
    payload = _scenario()
    payload["variant"] = "MDVRP"
    payload["depots"] = [payload["depot"]]
    payload["depot"] = None
    with pytest.raises(FuelError, match="two depots"):
        validate_scenario(FuelScenario.model_validate(payload))


def test_build_mdvrp_puts_depots_first_without_time():
    payload = _scenario()
    payload["variant"] = "MDVRP"
    second = dict(payload["depot"])
    second["name"] = "North"
    second["lat"] = 51.51
    payload["depots"] = [payload["depot"], second]
    payload["depot"] = None
    distance = np.zeros((3, 3))
    travel = np.zeros((3, 3))
    instance = build_fuel_instance(FuelScenario.model_validate(payload), distance, travel)
    assert instance.variant == "MDVRP"
    assert instance.depot_indices == (0, 1)
    assert list(instance.customers) == [2]
    assert instance.time_windows is None
    assert instance.travel_times is None
    assert int(instance.demands[2]) == 40


def test_route_distances_return_to_the_assigned_depot():
    distance = np.array([[0.0, 1.0, 5.0], [1.0, 0.0, 2.0], [5.0, 2.0, 0.0]])
    assert route_distances(distance, [[2]], [1])["route_km"] == pytest.approx([4.0])
    assert route_distances(distance, [[2]])["leg_km"][0] == pytest.approx([5.0, 5.0])


def test_cvrp_job_reports_kilometers_without_a_clock(monkeypatch: pytest.MonkeyPatch):
    def fake_get(url: str) -> dict:
        if "/table/" in url:
            return _table()
        if "/route/" in url:
            return _route()
        raise AssertionError(url)

    payload = _scenario()
    payload["variant"] = "CVRP"
    monkeypatch.setattr("web.api.fueling._get_json", fake_get)
    created = client.post(
        "/api/fueling/jobs",
        json={"scenario": payload, "solver": "pyvrp", "time_budget_s": 2, "seed": 0},
    )
    assert created.status_code == 200, created.text
    record = _wait(created.json()["id"])
    assert record["status"] == "ok", record
    result = record["result"]
    assert result["depart_min"] == []
    assert result["arrivals_min"] == []
    assert result["route_depots"] == []
    assert result["objective"] == pytest.approx(4.0, abs=1e-2)
    assert result["obj_mismatch"] == pytest.approx(0.0, abs=1e-2)
    assert result["paths"][0]["geometry"] == STREET


def test_mdvrp_job_assigns_a_depot_and_skips_the_clock(monkeypatch: pytest.MonkeyPatch):
    def fake_get(url: str) -> dict:
        if "/table/" in url:
            return {
                "code": "Ok",
                "durations": [[0, 60, 600], [60, 0, 120], [600, 120, 0]],
                "distances": [[0, 1000, 5000], [1000, 0, 2000], [5000, 2000, 0]],
            }
        if "/route/" in url:
            return _route()
        raise AssertionError(url)

    payload = _scenario()
    payload["variant"] = "MDVRP"
    second = dict(payload["depot"])
    second["name"] = "North"
    second["lat"] = 51.51
    payload["depots"] = [payload["depot"], second]
    payload["depot"] = None
    monkeypatch.setattr("web.api.fueling._get_json", fake_get)
    created = client.post(
        "/api/fueling/jobs",
        json={"scenario": payload, "solver": "pyvrp", "time_budget_s": 2, "seed": 0},
    )
    assert created.status_code == 200, created.text
    record = _wait(created.json()["id"])
    assert record["status"] == "ok", record
    result = record["result"]
    assert result["depart_min"] == []
    assert result["route_depots"]
    assert result["route_depots"][0] in (0, 1)
    assert result["obj_mismatch"] == pytest.approx(0.0, abs=1e-2)
    assert result["paths"][0]["stops"] == result["routes"][0]


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
