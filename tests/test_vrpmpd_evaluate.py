"""Tests for VRPMPD position-dependent capacity checking."""

from __future__ import annotations

import numpy as np
import pytest

from vrpbench.core import evaluate
from vrpbench.core.instance import VRPMPD, Instance
from vrpbench.core.solution import Solution


def _make_vrpmpd_instance(
    *,
    pickups,
    deliveries,
    capacity: int,
    num_nodes: int | None = None,
) -> Instance:
    """Build a minimal VRPMPD instance on a straight-line grid."""
    n = num_nodes if num_nodes is not None else len(pickups)
    coords = np.array([[float(i), 0.0] for i in range(n)])
    diff = coords[:, None, :] - coords[None, :, :]
    distance = np.sqrt((diff**2).sum(axis=-1))
    p = np.array(pickups, dtype=int)
    d = np.array(deliveries, dtype=int)
    return Instance(
        name="toy-vrpmpd",
        variant=VRPMPD,
        num_nodes=n,
        coords=coords,
        demands=d,
        capacity=capacity,
        distance=distance,
        depot=0,
        pickups=p,
        deliveries=d,
    )


# ---------------------------------------------------------------------------
# Topology:
#   depot (index 0): pickup=0, delivery=0
#   customer 1: delivery=5, pickup=0   (receives 5 units)
#   customer 2: delivery=0, pickup=3   (ships 3 units back)
#   customer 3: delivery=4, pickup=0   (receives 4 units)
#
# Route [1, 2, 3], capacity 12:
#   depart load = 5 + 0 + 4 = 9          <= 12 OK
#   after c1 (deliver 5): 9 - 5 = 4      <= 12 OK
#   after c2 (pickup 3):  4 + 3 = 7      <= 12 OK
#   after c3 (deliver 4): 7 - 4 = 3      <= 12 OK  -> feasible
#
# Route [1, 3, 2], capacity 12:  (same goods, different order)
#   depart load = 9   <= 12 OK
#   after c1 (deliver 5): 4   OK
#   after c3 (deliver 4): 0   OK
#   after c2 (pickup 3):  3   OK  -> also feasible (order didn't matter here)
#
# To force a mid-route violation we shrink capacity to 8 on route [1, 2, 3]:
#   depart load = 9 > 8 -> departure violation (caught at route level)
#
# Better: capacity=9, route [2, 1, 3]:
#   depart load = 0 + 5 + 4 = 9  <= 9 OK
#   after c2 (pickup 3): 9 + 3 = 12 > 9 -> MID-ROUTE violation
# ---------------------------------------------------------------------------

PICKUPS    = [0, 0, 3, 0]   # depot, c1, c2, c3
DELIVERIES = [0, 5, 0, 4]   # depot, c1, c2, c3


def test_vrpmpd_feasible_route():
    inst = _make_vrpmpd_instance(pickups=PICKUPS, deliveries=DELIVERIES, capacity=12)
    sol = Solution(routes=[[1, 2, 3]], objective=0.0, feasible=True, runtime_s=0.0)
    ev = evaluate.verify(inst, sol)
    assert ev.feasible, ev.violations
    assert ev.num_vehicles == 1


def test_vrpmpd_departure_load_exceeds_capacity():
    # capacity=8 but depart load for route [1,2,3] = 9 -> violation at departure.
    inst = _make_vrpmpd_instance(pickups=PICKUPS, deliveries=DELIVERIES, capacity=8)
    sol = Solution(routes=[[1, 2, 3]], objective=0.0, feasible=True, runtime_s=0.0)
    ev = evaluate.verify(inst, sol)
    assert not ev.feasible
    assert any("departure load" in v for v in ev.violations)


def test_vrpmpd_mid_route_capacity_violation():
    # Route [2, 1, 3], capacity=9:
    # depart = 0+5+4=9 <= 9  OK
    # after c2 (pickup 3): 9+3=12 > 9 -> violation at customer 2.
    inst = _make_vrpmpd_instance(pickups=PICKUPS, deliveries=DELIVERIES, capacity=9)
    sol = Solution(routes=[[2, 1, 3]], objective=0.0, feasible=True, runtime_s=0.0)
    ev = evaluate.verify(inst, sol)
    assert not ev.feasible
    assert any("customer 2" in v and "capacity" in v for v in ev.violations)


def test_vrpmpd_feasible_permutation_depends_on_order():
    # With capacity=9 route [1, 2, 3] is infeasible at departure (load=9 <= 9 is OK
    # but after c2: 4+3=7 OK), actually:
    # depart=9, after c1 del 5: 4, after c2 pick 3: 7, after c3 del 4: 3 -> feasible.
    inst = _make_vrpmpd_instance(pickups=PICKUPS, deliveries=DELIVERIES, capacity=9)
    sol = Solution(routes=[[1, 2, 3]], objective=0.0, feasible=True, runtime_s=0.0)
    ev = evaluate.verify(inst, sol)
    assert ev.feasible, ev.violations


def test_vrpmpd_missing_customer_flagged():
    inst = _make_vrpmpd_instance(pickups=PICKUPS, deliveries=DELIVERIES, capacity=20)
    # Only serve 1 and 2, skip 3.
    sol = Solution(routes=[[1, 2]], objective=0.0, feasible=True, runtime_s=0.0)
    ev = evaluate.verify(inst, sol)
    assert not ev.feasible
    assert any("unvisited" in v for v in ev.violations)


def test_vrpmpd_objective_recomputed_correctly():
    # Straight-line coords: depot=0, c1=1, c2=2, c3=3.
    # Route [1, 2, 3]: 0->1 + 1->2 + 2->3 + 3->0 = 1+1+1+3 = 6.
    inst = _make_vrpmpd_instance(pickups=PICKUPS, deliveries=DELIVERIES, capacity=12)
    sol = Solution(routes=[[1, 2, 3]], objective=999.0, feasible=True, runtime_s=0.0)
    ev = evaluate.verify(inst, sol)
    assert ev.objective == pytest.approx(6.0)
    assert ev.obj_mismatch == pytest.approx(993.0)


def test_vrpmpd_num_vehicles_counted():
    inst = _make_vrpmpd_instance(pickups=PICKUPS, deliveries=DELIVERIES, capacity=12)
    # Split into two routes.
    sol = Solution(
        routes=[[1, 2], [3]], objective=0.0, feasible=True, runtime_s=0.0
    )
    ev = evaluate.verify(inst, sol)
    assert ev.num_vehicles == 2
