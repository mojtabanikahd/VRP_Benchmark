"""Tests for PVRP constraint checking and objective recomputation.

Day-combination codes are bitmasks over the t days (bit d <-> day d, 0-indexed):
code 1 = day 0; code 2 = day 1; code 3 = days 0 and 1.
"""

from __future__ import annotations

import numpy as np
import pytest

from vrpbench.core import evaluate
from vrpbench.core.instance import PVRP, Instance
from vrpbench.core.solution import Solution


def _line_instance(
    *,
    combinations,
    freq,
    periods,
    m,
    capacity,
    n_customers,
    demands=None,
    spacing=1.0,
    max_route_duration=0.0,
    services=None,
):
    """Build a PVRP instance with customers on a straight line at x = i*spacing."""
    n = n_customers + 1
    coords = np.array([[float(i) * spacing, 0.0] for i in range(n)])
    diff = coords[:, None, :] - coords[None, :, :]
    distance = np.rint(np.sqrt((diff**2).sum(axis=-1)))
    if demands is None:
        demands = [0] + [1] * n_customers
    if services is None:
        services = [0.0] * n
    return Instance(
        name="toy-pvrp",
        variant=PVRP,
        num_nodes=n,
        coords=coords,
        demands=np.array(demands, dtype=int),
        capacity=capacity,
        distance=distance,
        depot=0,
        periods=periods,
        freq=np.array(freq, dtype=int),
        combinations=combinations,
        max_vehicles_per_day=m,
        max_route_duration=max_route_duration,
        service_times=np.array(services, dtype=float),
    )


# depot + 3 customers; c1 day0-only, c2 day1-only, c3 both days.
COMBOS = [[], [1], [2], [3]]
FREQ = [0, 1, 1, 2]


def test_pvrp_feasible_solution_passes_with_correct_objective():
    inst = _line_instance(
        combinations=COMBOS, freq=FREQ, periods=2, m=2, capacity=10, n_customers=3
    )
    # day 0: visit c1 and c3; day 1: visit c2 and c3.
    sol = Solution(
        routes=[[1, 3], [2, 3]],
        objective=12.0,
        feasible=True,
        runtime_s=0.0,
        route_days=[0, 1],
    )
    ev = evaluate.verify(inst, sol)
    assert ev.feasible, ev.violations
    # 0->1->3->0 = 1+2+3 = 6 ; 0->2->3->0 = 2+1+3 = 6 ; total 12.
    assert ev.objective == pytest.approx(12.0)
    assert ev.obj_mismatch == pytest.approx(0.0)


def test_pvrp_combination_violation_flagged():
    inst = _line_instance(
        combinations=COMBOS, freq=FREQ, periods=2, m=2, capacity=10, n_customers=3
    )
    # c1 is day0-only ([1]) but here it is visited on day 1 -> pattern {1} not allowed.
    sol = Solution(
        routes=[[3], [1, 2, 3]],
        objective=0.0,
        feasible=True,
        runtime_s=0.0,
        route_days=[0, 1],
    )
    ev = evaluate.verify(inst, sol)
    assert not ev.feasible
    assert any("customer 1" in v and "combination" in v for v in ev.violations)


def test_pvrp_vehicle_cap_violation_flagged():
    # m = 1, but day 0 uses two routes.
    inst = _line_instance(
        combinations=COMBOS, freq=FREQ, periods=2, m=1, capacity=10, n_customers=3
    )
    sol = Solution(
        routes=[[1], [3], [2, 3]],
        objective=0.0,
        feasible=True,
        runtime_s=0.0,
        route_days=[0, 0, 1],
    )
    ev = evaluate.verify(inst, sol)
    assert not ev.feasible
    assert any("max vehicles/day" in v for v in ev.violations)


def test_pvrp_capacity_violation_flagged():
    inst = _line_instance(
        combinations=COMBOS,
        freq=FREQ,
        periods=2,
        m=2,
        capacity=1,  # each customer demand 1, so a 2-customer route overloads
        n_customers=3,
    )
    sol = Solution(
        routes=[[1, 3], [2, 3]],
        objective=0.0,
        feasible=True,
        runtime_s=0.0,
        route_days=[0, 1],
    )
    ev = evaluate.verify(inst, sol)
    assert not ev.feasible
    assert any("capacity" in v for v in ev.violations)


def test_pvrp_duration_violation_flagged():
    # Single day; customers far apart with service time so travel+service > maxdur.
    # depot at 0, c1 at 10, c2 at 20. Route [1,2] day 0:
    #   travel = 10 + 10 + 20 = 40 ; service = 5 + 5 = 10 ; total 50 > maxdur 45.
    inst = _line_instance(
        combinations=[[], [1], [1]],
        freq=[0, 1, 1],
        periods=1,
        m=1,
        capacity=100,
        n_customers=2,
        spacing=10.0,
        max_route_duration=45.0,
        services=[0.0, 5.0, 5.0],
    )
    sol = Solution(
        routes=[[1, 2]],
        objective=0.0,
        feasible=True,
        runtime_s=0.0,
        route_days=[0],
    )
    ev = evaluate.verify(inst, sol)
    assert not ev.feasible
    assert any("duration" in v for v in ev.violations)


def test_pvrp_route_days_length_mismatch_flagged():
    inst = _line_instance(
        combinations=COMBOS, freq=FREQ, periods=2, m=2, capacity=10, n_customers=3
    )
    sol = Solution(
        routes=[[1, 3], [2, 3]],
        objective=0.0,
        feasible=True,
        runtime_s=0.0,
        route_days=[0],  # only one day for two routes
    )
    ev = evaluate.verify(inst, sol)
    assert not ev.feasible
    assert any("route_days length" in v for v in ev.violations)
