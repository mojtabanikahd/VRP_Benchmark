"""PVRP adapter — a shared wrapper that turns any CVRP/VRPTW base solver into a
Periodic VRP solver via an ALNS search over day-combination assignments.

None of the base solvers (PyVRP, VROOM, OR-Tools) support periodic routing
natively. ``PVRPSolver`` wraps one of them and:

* **Outer loop (ALNS).** Searches over the assignment of each customer to one of
  its *valid* day-combination bitmasks (so the per-customer frequency and
  allowed-combination constraints are respected *by construction* — operators only
  ever pick from a customer's own ``combinations``).
* **Inner loop (the base solver).** For a fixed assignment, each day is an
  independent CVRP (old set) or VRPTW (new set, to enforce the route-duration
  limit) sub-instance containing only that day's customers, solved by the wrapped
  base solver with a hard fleet cap of ``m`` vehicles.

Per-day routing is cached on the frozenset of that day's customers, so when ALNS
reassigns a handful of customers only the affected days are re-solved.

The reported objective is recomputed from the instance's authoritative distance
matrix over the reconstructed global routes (``evaluate.route_distance``), so it is
byte-identical to the evaluator's re-score (``obj_mismatch ≈ 0``). The base
solver's own objective is never trusted for the reported value.

The objective is total travel distance summed over all ``t`` days; ``m`` is a hard
per-day cap. A day the base solver cannot serve within ``m`` vehicles and capacity
(or, for the new set, the duration limit) contributes a large finite penalty, so
the simulated-annealing acceptance steers the search away from it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from vrpbench.core.evaluate import route_distance
from vrpbench.core.instance import CVRP, PVRP, VRPTW, Instance
from vrpbench.core.solution import Solution
from vrpbench.solvers.base import Solver, SolverError


def _days_of(code: int, periods: int) -> list[int]:
    """0-indexed days covered by a combination bitmask (bit d ↔ day d)."""
    return [d for d in range(periods) if (code >> d) & 1]


@dataclass
class _Context:
    """Immutable-ish shared context for the ALNS search (shared across states)."""

    instance: Instance
    base: Solver
    inner_budget_s: float
    seed: int
    m: int
    t: int
    capacity: int
    penalty: float
    # cache: frozenset(day customers) -> (global_routes, distance, feasible)
    day_cache: dict

    def solve_day(self, day_customers: list[int]):
        """Route one day's customers; cached on the customer set.

        Caching is deliberately conservative: only *reliable* outcomes are cached —
        a feasible solution, or the deterministic ``demand > m·capacity`` overload.
        A transient failure (the base solver raising ``SolverError``/returning no
        solution within the small inner budget, e.g. on a cold start) or a
        solved-but-infeasible result on a capacity-feasible day is **not** cached, so
        it is retried later instead of permanently poisoning a feasible day's entry.
        """
        key = frozenset(day_customers)
        cached = self.day_cache.get(key)
        if cached is not None:
            return cached

        inst = self.instance
        demand = int(sum(int(inst.demands[c]) for c in day_customers))
        if demand > self.m * self.capacity:
            # Provably infeasible with m vehicles — deterministic, safe to cache.
            res = ([], 0.0, False)
            self.day_cache[key] = res
            return res

        day_inst = _build_day_instance(inst, day_customers, self.m)
        try:
            sol = self.base.solve(
                day_inst, time_budget_s=self.inner_budget_s, seed=self.seed
            )
        except SolverError:
            return [], 0.0, False  # transient — do not cache, retry later

        # Map local indices (1..k) back to global customer indices.
        global_routes = [[day_customers[li - 1] for li in r] for r in sol.routes]
        feasible, dist = _eval_day(inst, global_routes, day_customers, self.m)
        res = (global_routes, dist, feasible)
        if feasible:
            self.day_cache[key] = res  # only cache reliable (feasible) solves
        return res


class _PVRPState:
    """ALNS state: an assignment of customers to chosen day-combination bitmasks.

    Implements the ``alns`` ``State`` protocol (``objective``); ``copy`` is used by
    the destroy operators. ``assignment`` maps every customer index to one of its
    valid combination codes; ``unassigned`` holds customers awaiting repair.
    """

    def __init__(self, assignment: dict[int, int], unassigned: list[int], ctx: _Context):
        self.assignment = assignment
        self.unassigned = unassigned
        self.ctx = ctx
        self.last_day_distance: list[float] | None = None

    def copy(self) -> "_PVRPState":
        st = _PVRPState(dict(self.assignment), list(self.unassigned), self.ctx)
        return st

    def day_customers(self, day: int) -> list[int]:
        return sorted(c for c, code in self.assignment.items() if (code >> day) & 1)

    def objective(self) -> float:
        ctx = self.ctx
        if self.unassigned:
            # Incomplete assignment (mid-repair) — should not be scored, but guard.
            return ctx.penalty * (self.t_penalty_units())
        total = 0.0
        infeasible = 0
        day_dist = [0.0] * ctx.t
        for d in range(ctx.t):
            dc = self.day_customers(d)
            if not dc:
                continue
            _routes, dist, feasible = ctx.solve_day(dc)
            day_dist[d] = dist
            total += dist
            if not feasible:
                infeasible += 1
        self.last_day_distance = day_dist
        return total + infeasible * ctx.penalty

    def t_penalty_units(self) -> int:
        return self.ctx.t + len(self.unassigned)


def _build_day_instance(instance: Instance, day_customers: list[int], m: int) -> Instance:
    """A compact CVRP/VRPTW sub-instance for one day (depot 0 + that day's customers).

    Local indices: 0 = depot, 1..k = ``day_customers`` in the given order. The
    distance sub-matrix is sliced from the authoritative matrix. ``max_vehicles`` is
    set to ``m`` so the base adapter caps the fleet at the per-day limit. When the
    instance has a route-duration limit (new set) the day is a VRPTW with synthetic
    windows ``[0, max_route_duration]`` on every node, which makes the base VRPTW
    adapter enforce ``travel + service ≤ max_route_duration`` per route.
    """
    nodes = [instance.depot] + day_customers
    idx = np.asarray(nodes)
    coords = instance.coords[idx]
    dist = instance.distance[np.ix_(idx, idx)]
    demands = np.asarray(
        [0] + [int(instance.demands[c]) for c in day_customers], dtype=int
    )
    k = len(day_customers)

    common = dict(
        name=f"{instance.name}-day",
        num_nodes=k + 1,
        coords=coords,
        demands=demands,
        capacity=int(instance.capacity),
        distance=dist,
        depot=0,
        num_vehicles=None,
        max_vehicles=int(m),
    )

    maxdur = instance.max_route_duration or 0.0
    if maxdur > 0:
        svc = instance.service_times
        assert svc is not None
        time_windows = np.array([[0.0, float(maxdur)]] * (k + 1), dtype=float)
        service_times = np.asarray(
            [0.0] + [float(svc[c]) for c in day_customers], dtype=float
        )
        return Instance(
            variant=VRPTW,
            time_windows=time_windows,
            service_times=service_times,
            **common,
        )
    return Instance(variant=CVRP, **common)


def _eval_day(
    instance: Instance, global_routes: list[list[int]], day_customers: list[int], m: int
) -> tuple[bool, float]:
    """Authoritative per-day feasibility + distance, independent of the base solver.

    Feasible iff every day customer is visited exactly once, at most ``m`` routes
    are used, no route exceeds capacity, and (new set) no route's travel+service
    exceeds the duration limit. Distance is summed from the authoritative matrix.
    """
    visited = [c for r in global_routes for c in r]
    dist = sum(route_distance(instance, r, instance.depot) for r in global_routes)
    if sorted(visited) != day_customers:  # missing, duplicate, or stray
        return False, dist
    if len(global_routes) > m:
        return False, dist
    cap = int(instance.capacity)
    maxdur = instance.max_route_duration or 0.0
    svc = instance.service_times
    for r in global_routes:
        if sum(int(instance.demands[c]) for c in r) > cap:
            return False, dist
        if maxdur > 0:
            assert svc is not None
            travel = route_distance(instance, r, instance.depot)
            service = sum(float(svc[c]) for c in r)
            if travel + service > maxdur + 1e-6:
                return False, dist
    return True, dist


# --------------------------------------------------------------------------- #
# Greedy initialisation + ALNS operators                                      #
# --------------------------------------------------------------------------- #


def _day_loads(assignment: dict[int, int], instance: Instance, t: int) -> np.ndarray:
    loads = np.zeros(t, dtype=float)
    for c, code in assignment.items():
        dem = int(instance.demands[c])
        for d in _days_of(code, t):
            loads[d] += dem
    return loads


def _greedy_assign(
    instance: Instance, multi: list[int], rng: np.random.Generator
) -> dict[int, int]:
    """Assign each customer a combination, balancing day-loads (fixed ones first)."""
    t = instance.periods
    combos = instance.combinations
    assert combos is not None
    assignment: dict[int, int] = {}
    loads = np.zeros(t, dtype=float)

    # Single-combination customers are forced.
    for c in range(1, instance.num_nodes):
        if len(combos[c]) == 1:
            code = combos[c][0]
            assignment[c] = code
            dem = int(instance.demands[c])
            for d in _days_of(code, t):
                loads[d] += dem

    # Multi-combination customers, in random order, minimising the resulting peak.
    order = list(multi)
    rng.shuffle(order)
    for c in order:
        dem = int(instance.demands[c])
        best_code, best_peak = None, float("inf")
        for code in combos[c]:
            proj = loads.copy()
            for d in _days_of(code, t):
                proj[d] += dem
            peak = float(proj.max())
            if peak < best_peak:
                best_peak, best_code = peak, code
        assignment[c] = int(best_code)
        for d in _days_of(int(best_code), t):
            loads[d] += dem
    return assignment


def _greedy_init(
    instance: Instance, multi: list[int], rng: np.random.Generator, restarts: int = 5
) -> dict[int, int]:
    """Best of a few greedy passes, keeping the one with the lowest peak day-load."""
    best_assign, best_peak = None, float("inf")
    for _ in range(max(1, restarts)):
        assign = _greedy_assign(instance, multi, rng)
        peak = float(_day_loads(assign, instance, instance.periods).max())
        if peak < best_peak:
            best_peak, best_assign = peak, assign
    assert best_assign is not None
    return best_assign


def _destroy_count(n_multi: int, rng: np.random.Generator) -> int:
    return int(rng.integers(1, max(2, n_multi // 4 + 1)))


def _random_destroy(state: _PVRPState, rng: np.random.Generator) -> _PVRPState:
    """Unassign k random multi-combination customers."""
    new = state.copy()
    multi = [c for c in new.assignment if len(new.ctx.instance.combinations[c]) > 1]
    if not multi:
        return new
    k = min(_destroy_count(len(multi), rng), len(multi))
    chosen = rng.choice(multi, size=k, replace=False)
    for c in chosen.tolist():
        new.unassigned.append(int(c))
        del new.assignment[int(c)]
    return new


def _worst_destroy(state: _PVRPState, rng: np.random.Generator) -> _PVRPState:
    """Unassign multi-combo customers on the highest-distance day (largest demand first)."""
    if state.last_day_distance is None:
        state.objective()  # populate per-day distances
    new = state.copy()
    instance = new.ctx.instance
    combos = instance.combinations
    day_dist = state.last_day_distance or [0.0] * new.ctx.t
    # Days ranked by current routing distance, descending.
    ranked_days = sorted(range(new.ctx.t), key=lambda d: day_dist[d], reverse=True)
    multi_all = [c for c in new.assignment if len(combos[c]) > 1]
    if not multi_all:
        return new
    k = min(_destroy_count(len(multi_all), rng), len(multi_all))
    removed = 0
    for d in ranked_days:
        on_day = [
            c for c in list(new.assignment)
            if len(combos[c]) > 1 and (new.assignment[c] >> d) & 1
        ]
        on_day.sort(key=lambda c: int(instance.demands[c]), reverse=True)
        for c in on_day:
            if removed >= k:
                break
            if c in new.assignment:
                new.unassigned.append(c)
                del new.assignment[c]
                removed += 1
        if removed >= k:
            break
    return new


def _repair_common(state: _PVRPState, pick) -> _PVRPState:
    instance = state.ctx.instance
    combos = instance.combinations
    t = instance.periods
    # Random order of the unassigned customers.
    pending = state.unassigned
    state.unassigned = []
    for c in pending:
        loads = _day_loads(state.assignment, instance, t)
        code = pick(c, combos[c], loads, instance)
        state.assignment[c] = int(code)
    return state


def _greedy_repair(state: _PVRPState, rng: np.random.Generator) -> _PVRPState:
    """Reassign each unassigned customer the combo minimising the resulting peak day-load."""
    def pick(c, codes, loads, instance):
        dem = int(instance.demands[c])
        best_code, best_peak = None, float("inf")
        for code in codes:
            proj = loads.copy()
            for d in _days_of(code, instance.periods):
                proj[d] += dem
            peak = float(proj.max())
            if peak < best_peak:
                best_peak, best_code = peak, code
        return best_code

    return _repair_common(state, pick)


def _random_repair(state: _PVRPState, rng: np.random.Generator) -> _PVRPState:
    """Reassign each unassigned customer a uniformly random valid combo."""
    def pick(c, codes, loads, instance):
        return codes[int(rng.integers(0, len(codes)))]

    return _repair_common(state, pick)


class PVRPSolver:
    """Wrap a CVRP/VRPTW base solver into a Periodic VRP solver via ALNS."""

    supported_variants = (PVRP,)

    def __init__(self, base_solver: Solver) -> None:
        self.base = base_solver
        self.name = f"pvrp_{base_solver.name}"

    def version(self) -> str:
        return f"pvrp-alns+{self.base.version()}"

    def solve(self, instance: Instance, *, time_budget_s: float, seed: int) -> Solution:
        from alns import ALNS
        from alns.accept import SimulatedAnnealing
        from alns.select import RouletteWheel
        from alns.stop import MaxRuntime

        if instance.variant != PVRP:
            raise SolverError(f"PVRPSolver does not support {instance.variant!r}")
        if instance.depot != 0:
            raise SolverError("PVRPSolver assumes depot at index 0")

        start = time.perf_counter()
        t = instance.periods
        m = instance.max_vehicles_per_day
        combos = instance.combinations
        assert t is not None and m is not None and combos is not None

        # Penalty per infeasible day: an upper bound on any full-horizon distance,
        # so a feasible solution always beats an infeasible one (kept finite for SA).
        penalty = float(t) * float(instance.num_nodes) * float(instance.distance.max()) + 1.0
        inner_budget = min(5.0, max(0.2, time_budget_s / (t * 30)))

        ctx = _Context(
            instance=instance,
            base=self.base,
            inner_budget_s=inner_budget,
            seed=seed,
            m=int(m),
            t=int(t),
            capacity=int(instance.capacity),
            penalty=penalty,
            day_cache={},
        )

        rng = np.random.default_rng(seed)
        multi = [c for c in range(1, instance.num_nodes) if len(combos[c]) > 1]
        init_assign = _greedy_init(instance, multi, rng)
        state = _PVRPState(init_assign, [], ctx)

        if multi:
            init_obj = state.objective()
            elapsed = time.perf_counter() - start
            remaining = max(0.1, time_budget_s - elapsed)

            alns = ALNS(rng)
            alns.add_destroy_operator(_random_destroy)
            alns.add_destroy_operator(_worst_destroy)
            alns.add_repair_operator(_greedy_repair)
            alns.add_repair_operator(_random_repair)
            select = RouletteWheel(scores=[5, 2, 1, 0.5], decay=0.8, num_destroy=2, num_repair=2)
            accept = SimulatedAnnealing.autofit(max(init_obj, 1.0), 0.05, 0.50, 1000)
            result = alns.iterate(state, select, accept, MaxRuntime(remaining))
            best = result.best_state
        else:
            best = state  # nothing to search over; the forced assignment is the answer

        routes, route_days, objective, feasible = _extract(best, ctx)
        runtime_s = time.perf_counter() - start
        return Solution(
            routes=routes,
            objective=objective,
            feasible=feasible,
            runtime_s=runtime_s,
            route_days=route_days,
        )


def _extract(state: _PVRPState, ctx: _Context):
    """Rebuild global routes + per-route day tags from the best assignment."""
    routes: list[list[int]] = []
    route_days: list[int] = []
    objective = 0.0
    feasible = True
    for d in range(ctx.t):
        dc = state.day_customers(d)
        if not dc:
            continue
        day_routes, dist, day_ok = ctx.solve_day(dc)
        if not day_ok:
            feasible = False
        for r in day_routes:
            routes.append(r)
            route_days.append(d)
        objective += dist
    return routes, route_days, float(objective), feasible
