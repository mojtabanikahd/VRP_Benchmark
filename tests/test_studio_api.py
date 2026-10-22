"""HTTP catalog, upload, and solve jobs for the route studio."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from web.api.main import app

DATA = Path(__file__).parent / "data"
client = TestClient(app)


def _cvrp_payload() -> dict:
    return {
        "scenario": {
            "name": "toy",
            "variant": "CVRP",
            "capacity": 2,
            "nodes": [
                {"role": "depot", "x": 0, "y": 0, "demand": 0},
                {"role": "customer", "x": 1, "y": 0, "demand": 1},
                {"role": "customer", "x": 2, "y": 0, "demand": 1},
                {"role": "customer", "x": 3, "y": 0, "demand": 1},
            ],
        },
        "solver": "pyvrp",
        "time_budget_s": 2,
        "seed": 0,
    }


def test_catalog_lists_three_variants_and_hides_pvrp():
    response = client.get("/api/catalog")
    assert response.status_code == 200
    body = response.json()
    names = [item["variant"] for item in body["variants"]]
    assert names == ["CVRP", "VRPTW", "MDVRP"]
    assert "PVRP" not in names
    by_variant = {item["variant"]: {s["name"] for s in item["solvers"]} for item in body["variants"]}
    assert {"pyvrp", "ortools", "vroom", "vrpsolvereasy"} <= by_variant["CVRP"]
    assert "vrpsolvereasy" not in by_variant["MDVRP"]
    assert "pyvrp" in by_variant["MDVRP"]
    assert not any(name.startswith("pvrp_") for solvers in by_variant.values() for name in solvers)


def test_preview_rejects_pvrp():
    payload = _cvrp_payload()["scenario"]
    payload["variant"] = "PVRP"
    response = client.post("/api/scenarios/preview", json=payload)
    assert response.status_code == 422
    assert "PVRP" in response.text


def test_upload_cvrp_and_mdvrp():
    with (DATA / "toy.vrp").open("rb") as handle:
        response = client.post(
            "/api/instances/upload",
            data={"variant": "CVRP"},
            files={"file": ("toy.vrp", handle, "text/plain")},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["num_customers"] == 3
    assert body["num_depots"] == 1
    assert body["distance_kind"] == "euclidean_rint"

    with (DATA / "toy_mdvrp.txt").open("rb") as handle:
        response = client.post(
            "/api/instances/upload",
            data={"variant": "MDVRP"},
            files={"file": ("toy_mdvrp.txt", handle, "text/plain")},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["num_depots"] == 2
    assert body["num_customers"] == 4


def test_pyvrp_job_verifies():
    created = client.post("/api/jobs", json=_cvrp_payload())
    assert created.status_code == 200, created.text
    job_id = created.json()["id"]
    record = None
    deadline = time.time() + 30
    while time.time() < deadline:
        record = client.get(f"/api/jobs/{job_id}").json()
        if record["status"] in {"ok", "error"}:
            break
        time.sleep(0.2)
    assert record is not None
    assert record["status"] == "ok", record
    result = record["result"]
    assert result["feasible"] is True
    assert result["objective"] == pytest.approx(8.0)
    assert result["obj_mismatch"] == pytest.approx(0.0, abs=1e-6)
    assert result["routes"]
