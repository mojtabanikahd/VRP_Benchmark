"""Tests for SDVRP constraint checking and objective recomputation.

The instance has a heterogeneous, site-dependent fleet: vehicle types are 0-indexed
and each has its own capacity (and optionally a max route duration). ``allowed_types``
gives the set of types that may serve each node, and a customer's demand may be split
across several routes (with the per-route quantities summing to the demand).
"""

from __future__ import annotations

import numpy as np
import pytest

from vrpbench.core import evaluate
from vrpbench.core.instance import SDVRP, Instance
from vrpbench.core.solution import Solution


def _toy(
    *,
    caps,
    durs,
    allowed,
    demands,
    m,
    spacing=1.0,
    services=None,
):
    """Build an SDVRP instance with customers on a straight line at x = i*spacing."""
    n = len(demands)
    coords = np.array([[float(i) * spacing, 0.0] for i in range(n)])
    diff = coords[:, None, :] - coords[None, :, :]
    distance = np.rint(np.sqrt((diff**2).sum(axis=-1)))
    if services is None:
        services = [0.0] * n
    return Instance(
        name="toy-sdvrp",
        variant=SDVRP,
        num_nodes=n,
        coords=coords,
        demands=np.array(demands, dtype=int),
        capacity=int(max(caps)),
        distance=distance,
        depot=0,
        num_vehicle_types=len(caps),
        vehicle_capacities=tuple(caps),
        vehicle_durations=tuple(float(d) for d in durs),
        vehicles_per_type=m,
        allowed_types=[frozenset(a) for a in allowed],
        service_times=np.array(services, dtype=float),
    )


# depot + 3 customers; c1/c3 allow both types, c2 only type 1.
ALLOWED = [set(), {0, 1}, {1}, {0, 1}]
DEMANDS = [0, 5, 8, 15]
CAPS = (10, 20)
DURS = (0.0, 0.0)


def test_sdvrp_feasible_split_solution_passes():
    inst = _toy(caps=CAPS, durs=DURS, allowed=ALLOWED, demands=DEMANDS, m=2)
    # c3 (demand 15) is split: 12 on a type-1 route, 3 on a type-0 route.
    sol = Solution(
        routes=[[2, 3], [1, 3]],
        objective=12.0,
        feasible=True,
        runtime_s=0.0,
        route_vehicle_types=[1, 0],
        route_deliveries=[{2: 8, 3: 12}, {1: 5, 3: 3}],
    )
    ev = evaluate.verify(inst, sol)
    assert ev.feasible, ev.violations
    # 0->2->3->0 = 2+1+3 = 6 ; 0->1->3->0 = 1+2+3 = 6 ; total 12.
    assert ev.objective == pytest.approx(12.0)
    assert ev.obj_mismatch == pytest.approx(0.0)


def test_sdvrp_capacity_violation_flagged():
    inst = _toy(caps=CAPS, durs=DURS, allowed=ALLOWED, demands=DEMANDS, m=2)
    # one type-1 route carries everything: load 5+8+15 = 28 > capacity 20.
    sol = Solution(
        routes=[[1, 2, 3]],
        objective=0.0,
        feasible=True,
        runtime_s=0.0,
        route_vehicle_types=[1],
        route_deliveries=[{1: 5, 2: 8, 3: 15}],
    )
    ev = evaluate.verify(inst, sol)
    assert not ev.feasible
    assert any("capacity" in v for v in ev.violations)


def test_sdvrp_site_dependency_violation_flagged():
    inst = _toy(caps=CAPS, durs=DURS, allowed=ALLOWED, demands=DEMANDS, m=2)
    # c2 only allows type 1, but here it is on a type-0 route.
    sol = Solution(
        routes=[[2], [1, 3]],
        objective=0.0,
        feasible=True,
        runtime_s=0.0,
        route_vehicle_types=[0, 1],
        route_deliveries=[{2: 8}, {1: 5, 3: 15}],
    )
    ev = evaluate.verify(inst, sol)
    assert not ev.feasible
    assert any("cannot be served by vehicle type" in v for v in ev.violations)


def test_sdvrp_demand_coverage_violation_flagged():
    inst = _toy(caps=CAPS, durs=DURS, allowed=ALLOWED, demands=DEMANDS, m=2)
    # c3 needs 15 but only 10 is delivered.
    sol = Solution(
        routes=[[2, 3], [1]],
        objective=0.0,
        feasible=True,
        runtime_s=0.0,
        route_vehicle_types=[1, 0],
        route_deliveries=[{2: 8, 3: 10}, {1: 5}],
    )
    ev = evaluate.verify(inst, sol)
    assert not ev.feasible
    assert any("required demand" in v for v in ev.violations)


def test_sdvrp_fleet_cap_violation_flagged():
    # m = 1 vehicle per type, but three type-1 routes are used.
    inst = _toy(caps=CAPS, durs=DURS, allowed=ALLOWED, demands=DEMANDS, m=1)
    sol = Solution(
        routes=[[1], [2], [3]],
        objective=0.0,
        feasible=True,
        runtime_s=0.0,
        route_vehicle_types=[1, 1, 1],
        route_deliveries=[{1: 5}, {2: 8}, {3: 15}],
    )
    ev = evaluate.verify(inst, sol)
    assert not ev.feasible
    assert any("max vehicles/type" in v for v in ev.violations)


def test_sdvrp_duration_violation_flagged():
    # type 1 has a 30-unit duration limit; customers spaced 10 apart.
    # route [1,2,3]: travel 0->10->20->30->0 = 10+10+10+30 = 60 > 30.
    inst = _toy(
        caps=(100, 100),
        durs=(0.0, 30.0),
        allowed=[set(), {1}, {1}, {1}],
        demands=[0, 1, 1, 1],
        m=3,
        spacing=10.0,
    )
    sol = Solution(
        routes=[[1, 2, 3]],
        objective=0.0,
        feasible=True,
        runtime_s=0.0,
        route_vehicle_types=[1],
        route_deliveries=[{1: 1, 2: 1, 3: 1}],
    )
    ev = evaluate.verify(inst, sol)
    assert not ev.feasible
    assert any("duration" in v for v in ev.violations)


def test_sdvrp_delivery_keys_must_match_route():
    inst = _toy(caps=CAPS, durs=DURS, allowed=ALLOWED, demands=DEMANDS, m=2)
    # route_deliveries omits customer 3, which the route visits.
    sol = Solution(
        routes=[[2, 3], [1, 3]],
        objective=0.0,
        feasible=True,
        runtime_s=0.0,
        route_vehicle_types=[1, 0],
        route_deliveries=[{2: 8}, {1: 5, 3: 15}],
    )
    ev = evaluate.verify(inst, sol)
    assert not ev.feasible
    assert any("do not match route customers" in v for v in ev.violations)
