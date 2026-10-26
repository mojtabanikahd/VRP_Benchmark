"""In-process solve jobs.

One worker thread runs solves in order. A second request waits in the queue
instead of sharing the solver process.
"""

import queue
import threading
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

from vrpbench.core import evaluate
from vrpbench.solvers import get_solver
from vrpbench.solvers.base import SolverError

from web.api.fueling import FuelJobRequest, FuelWork, ensure_fuel_solver, solve_fuel_job, validate_scenario
from web.api.scenario import STUDIO_VARIANTS, Scenario, ScenarioError, build_instance, canonicalize

JobStatus = Literal["queued", "running", "ok", "error"]


class JobRequest(BaseModel):
    scenario: Scenario
    solver: str
    time_budget_s: float = Field(default=10, gt=0, le=300)
    seed: int = Field(default=0, ge=0)


class JobRecord(BaseModel):
    id: str
    status: JobStatus
    error: str | None = None
    result: dict[str, Any] | None = None


class _Job:
    def __init__(self, request: JobRequest | None = None, *, fuel: FuelWork | None = None) -> None:
        if (request is None) == (fuel is None):
            raise RuntimeError("a job is either a studio request or a fueling scenario")
        self.id = uuid.uuid4().hex
        self.request = request
        self.fuel = fuel
        self.status: JobStatus = "queued"
        self.error: str | None = None
        self.result: dict[str, Any] | None = None

    def view(self) -> JobRecord:
        return JobRecord(
            id=self.id,
            status=self.status,
            error=self.error,
            result=self.result,
        )


class JobRunner:
    def __init__(self) -> None:
        self._jobs: dict[str, _Job] = {}
        self._lock = threading.Lock()
        self._queue: queue.Queue[str] = queue.Queue()
        self._thread = threading.Thread(target=self._loop, name="vrp-studio-solve", daemon=True)
        self._thread.start()

    def submit(self, request: JobRequest) -> JobRecord:
        request = request.model_copy(
            update={"scenario": canonicalize(request.scenario)}
        )
        _check_solver(request)
        build_instance(request.scenario)
        job = _Job(request)
        with self._lock:
            self._jobs[job.id] = job
        self._queue.put(job.id)
        return job.view()

    def submit_fuel(self, request: FuelJobRequest) -> JobRecord:
        validate_scenario(request.scenario)
        ensure_fuel_solver(request.solver, request.scenario.variant)
        job = _Job(
            fuel=FuelWork(
                scenario=request.scenario,
                solver=request.solver,
                time_budget_s=request.time_budget_s,
                seed=request.seed,
            )
        )
        with self._lock:
            self._jobs[job.id] = job
        self._queue.put(job.id)
        return job.view()

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.view() if job is not None else None

    def _loop(self) -> None:
        while True:
            job_id = self._queue.get()
            with self._lock:
                job = self._jobs[job_id]
                job.status = "running"
            try:
                if job.fuel is not None:
                    result = solve_fuel_job(job.fuel)
                else:
                    assert job.request is not None
                    result = _solve(job.request)
            except Exception as exc:  # solver failures stay on the job
                with self._lock:
                    job.status = "error"
                    job.error = str(exc)
            else:
                with self._lock:
                    job.status = "ok"
                    job.result = result
            finally:
                self._queue.task_done()


def _check_solver(request: JobRequest) -> None:
    if request.scenario.variant not in STUDIO_VARIANTS:
        raise ScenarioError(
            f"unsupported variant {request.scenario.variant!r}; expected one of {STUDIO_VARIANTS}"
        )
    try:
        solver = get_solver(request.solver)
    except KeyError as exc:
        raise ScenarioError(str(exc)) from exc
    if request.scenario.variant not in solver.supported_variants:
        raise ScenarioError(
            f"solver {request.solver!r} does not support {request.scenario.variant}"
        )


def _solve(request: JobRequest) -> dict[str, Any]:
    instance = build_instance(request.scenario)
    solver = get_solver(request.solver)
    try:
        solution = solver.solve(
            instance,
            time_budget_s=request.time_budget_s,
            seed=request.seed,
        )
    except SolverError as exc:
        raise ScenarioError(str(exc)) from exc
    checked = evaluate.verify(instance, solution)
    return {
        "routes": solution.routes,
        "route_depots": list(solution.route_depots),
        "objective": checked.objective,
        "solver_objective": solution.objective,
        "num_vehicles": checked.num_vehicles,
        "runtime_s": solution.runtime_s,
        "obj_mismatch": checked.obj_mismatch,
        "feasible": checked.feasible,
        "violations": list(checked.violations),
        "solver_version": solver.version(),
        "nodes": [node.model_dump() for node in request.scenario.nodes],
    }


_runner: JobRunner | None = None
_runner_lock = threading.Lock()


def get_runner() -> JobRunner:
    global _runner
    with _runner_lock:
        if _runner is None:
            _runner = JobRunner()
        return _runner
