"""FastAPI entrypoint for the VRP route studio."""

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from vrpbench.datasets.loader import load

from web.api.catalog import build_catalog
from web.api.fueling import FuelError, FuelJobRequest, fuel_catalog, search_places
from web.api.jobs import JobRequest, get_runner
from web.api.scenario import (
    STUDIO_VARIANTS,
    Scenario,
    ScenarioError,
    format_validation_error,
    preview_from_instance,
    preview_from_scenario,
)

app = FastAPI(title="VRP Route Studio", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _http_error(exc: Exception, status: int = 422) -> HTTPException:
    return HTTPException(status_code=status, detail=str(exc))


@app.get("/api/catalog")
def catalog() -> dict:
    return build_catalog()


@app.post("/api/scenarios/preview")
def preview_scenario(scenario: Scenario) -> dict:
    try:
        return preview_from_scenario(scenario).model_dump()
    except ScenarioError as exc:
        raise _http_error(exc) from exc


@app.post("/api/instances/upload")
async def upload_instance(
    variant: str = Form(...),
    file: UploadFile = File(...),
) -> dict:
    if variant not in STUDIO_VARIANTS:
        raise _http_error(
            ScenarioError(f"unsupported variant {variant!r}; expected one of {STUDIO_VARIANTS}")
        )
    suffix = Path(file.filename or "instance.txt").suffix or ".txt"
    payload = await file.read()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(payload)
        path = handle.name
    try:
        instance = load(path, variant=variant)
        return preview_from_instance(instance).model_dump()
    except (ScenarioError, ValueError, OSError) as exc:
        raise _http_error(exc) from exc
    finally:
        Path(path).unlink(missing_ok=True)


@app.get("/api/fueling/catalog")
def read_fuel_catalog() -> dict:
    return fuel_catalog()


@app.get("/api/fueling/geocode")
def geocode_address(q: str) -> dict:
    try:
        return {"places": search_places(q)}
    except FuelError as exc:
        raise _http_error(exc) from exc


@app.post("/api/fueling/jobs")
def create_fuel_job(body: FuelJobRequest) -> dict:
    try:
        return get_runner().submit_fuel(body).model_dump()
    except FuelError as exc:
        raise _http_error(exc) from exc


@app.post("/api/jobs")
def create_job(body: JobRequest) -> dict:
    try:
        return get_runner().submit(body).model_dump()
    except ScenarioError as exc:
        raise _http_error(exc) from exc
    except ValidationError as exc:
        raise _http_error(ScenarioError(format_validation_error(exc))) from exc


@app.get("/api/jobs/{job_id}")
def read_job(job_id: str) -> dict:
    record = get_runner().get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"unknown job {job_id}")
    return record.model_dump()
