"""SDVRP adapter — a Tabu Search for the site-dependent, heterogeneous-fleet VRP
with split delivery.

None of the base solvers (PyVRP, VROOM, OR-Tools) support site-dependency or split
delivery natively, so ``SDVRPSolver`` is a self-contained Tabu Search. It can run in
two modes, selected by the constructor:

* ``SDVRPSolver(None)`` → registry name ``sdvrp_tabu``. The initial solution is built
  by a greedy best-fit construction.
* ``SDVRPSolver(base)`` → ``sdvrp_pyvrp`` / ``sdvrp_ortools`` / ``sdvrp_vroom``. The
  *initial solution only* is informed by the wrapped base solver: it solves a relaxed
  homogeneous CVRP (single capacity = the largest vehicle type, ``max_vehicles = m·t``,
  site-dependency ignored) and the resulting customer ordering seeds the same best-fit
  construction, which is then improved by the same Tabu Search.

Fixed-slot fleet model
----------------------
The fleet is modelled as exactly ``m`` route slots per vehicle type — ``S = m·t`` slots
in total, each with a fixed type. A solution assigns customers (and split quantities) to
slots; an unused slot is simply an empty route. Because there are exactly ``m`` slots per
type, the **per-type fleet cap is satisfied structurally** and never appears as a
violation. The tight Cordeau instances (e.g. the new ``pr`` set has only ``m·t`` vehicles
for tens of customers) are precisely why split delivery matters: filling each vehicle to
its exact capacity usually requires splitting a customer across slots.

Search model (see CLAUDE.md):

* **State** = the ``S`` slot routes (customer sequences), their fixed types, and a
  per-slot ``{customer: quantity}`` delivery map. A split customer appears in several
  slots; its quantities always sum to its full demand (every operator and the
  construction preserve this, so demand coverage is invariant).
* **Cost** = total travel distance + a large finite ``penalty`` times the total
  infeasibility magnitude (per-slot capacity overflow + route-duration overflow + a
  heavily weighted count of site-incompatible visits). The magnitude form gives the
  search a gradient toward feasibility while the huge multiplier keeps any feasible
  solution strictly better than any infeasible one.
* **Operators** = Relocate, Swap, and Split Adjust, each using best-position insertion
  (the insertion point minimising the distance increase). Targets include empty slots,
  so the search can open routes of an under-used type.
* **Tabu list** = the last ``k = 20`` ``(customer, from_slot, to_slot)`` moves;
  **aspiration** overrides the tabu status when a move yields a new global best.
* **Stop** = wall-clock ``time_budget_s`` (primary) or ``no_improve_limit`` iterations
  without improvement (early exit). No fixed iteration cap — the time budget governs.

The reported objective is recomputed as pure travel distance over the final routes, so
it matches the evaluator's independent re-score (``obj_mismatch ≈ 0``); the penalised
cost is only an internal search proxy.
"""

from __future__ import annotations

import time
from collections import deque

import numpy as np

from vrpbench.core.instance import CVRP, SDVRP, Instance
from vrpbench.core.solution import Solution
from vrpbench.solvers.base import Solver, SolverError

# Bounds that keep each iteration cheap on the large instances (n up to ~417), so the
# wall-clock budget buys many iterations rather than a few exhaustive ones.
_MAX_RELOCATE_SEEDS = 80
_MAX_SWAP_TRIES = 200
_MAX_SPLIT_TRIES = 160


class _Ctx:
    """Read-only instance data + the fixed slot layout, shared by every state."""

    def __init__(self, instance: Instance, penalty: float) -> None:
        self.inst = instance
        self.dist = instance.distance
        self.depot = instance.depot
        self.demands = instance.demands
        self.caps = instance.vehicle_capacities
        self.durs = instance.vehicle_durations
        self.allowed = instance.allowed_types
        self.svc = instance.service_times
        self.t = int(instance.num_vehicle_types)
        self.m = int(instance.vehicles_per_type)
        self.penalty = penalty
        self.big_site = float(max(self.caps))  # a site violation outweighs cap overflow
        # Slot layout: m slots of type 0, then m of type 1, ... -> S = m*t slots.
        self.slot_type = [j for j in range(self.t) for _ in range(self.m)]
        self.n_slots = len(self.slot_type)

    def duration(self, route: list[int], vtype: int) -> float:
        travel = _route_distance(self.dist, route, self.depot)
        service = 0.0
        if self.svc is not None:
            service = float(sum(self.svc[c] for c in route))
        return travel + service

    def dur_ok(self, route: list[int], vtype: int) -> bool:
        if self.durs[vtype] <= 0:
            return True
        return self.duration(route, vtype) <= self.durs[vtype] + 1e-6

    def route_infeas(self, route: list[int], vtype: int, deliv: dict[int, int]) -> float:
        """Infeasibility magnitude of one slot (capacity + duration overflow + site)."""
        if not route:
            return 0.0
        inf = 0.0
        load = sum(deliv.values())
        if load > self.caps[vtype]:
            inf += float(load - self.caps[vtype])
        inf += self.big_site * sum(1 for c in route if vtype not in self.allowed[c])
        if self.durs[vtype] > 0:
            over = self.duration(route, vtype) - self.durs[vtype]
            if over > 0:
                inf += float(over)
        return inf


def _route_distance(dist: np.ndarray, route: list[int], depot: int) -> float:
    if not route:
        return 0.0
    total = dist[depot, route[0]]
    for a, b in zip(route, route[1:]):
        total += dist[a, b]
    total += dist[route[-1], depot]
    return float(total)


def _best_insert(dist: np.ndarray, route: list[int], c: int, depot: int) -> tuple[int, float]:
    """Cheapest position to insert ``c`` into ``route``; returns (index, distance increase)."""
    if not route:
        return 0, float(dist[depot, c] + dist[c, depot])
    best_pos, best_add = 0, float("inf")
    for p in range(len(route) + 1):
        a = depot if p == 0 else route[p - 1]
        b = depot if p == len(route) else route[p]
        add = float(dist[a, c] + dist[c, b] - dist[a, b])
        if add < best_add:
            best_add, best_pos = add, p
    return best_pos, best_add


class _State:
    """A mutable SDVRP solution over the fixed ``S = m·t`` slots, with cached costs."""

    def __init__(self, ctx: _Ctx, routes, deliveries) -> None:
        self.ctx = ctx
        self.routes: list[list[int]] = routes          # length S (some empty)
        self.deliveries: list[dict[int, int]] = deliveries  # length S
        self.refresh()

    @property
    def types(self) -> list[int]:
        return self.ctx.slot_type

    def copy(self) -> "_State":
        return _State(
            self.ctx,
            [list(r) for r in self.routes],
            [dict(d) for d in self.deliveries],
        )

    def refresh(self) -> None:
        ctx = self.ctx
        st = ctx.slot_type
        self.route_dist = [_route_distance(ctx.dist, r, ctx.depot) for r in self.routes]
        self.route_inf = [
            ctx.route_infeas(r, st[i], d)
            for i, (r, d) in enumerate(zip(self.routes, self.deliveries))
        ]
        self.total_dist = float(sum(self.route_dist))
        self.total_inf = float(sum(self.route_inf))

    def cost(self) -> float:
        return self.total_dist + self.ctx.penalty * self.total_inf

    def is_feasible(self) -> bool:
        return self.total_inf <= 1e-6

    def delta(self, changes: dict[int, tuple[list[int], dict[int, int]]]) -> float:
        ctx = self.ctx
        st = ctx.slot_type
        d_dist = 0.0
        d_inf = 0.0
        for idx, (rl, dl) in changes.items():
            d_dist += _route_distance(ctx.dist, rl, ctx.depot) - self.route_dist[idx]
            d_inf += ctx.route_infeas(rl, st[idx], dl) - self.route_inf[idx]
        return d_dist + ctx.penalty * d_inf

    def apply(self, changes: dict[int, tuple[list[int], dict[int, int]]]) -> None:
        for idx, (rl, dl) in changes.items():
            self.routes[idx] = rl
            self.deliveries[idx] = dl
        self.refresh()


# --------------------------------------------------------------------------- #
# Construction                                                                #
# --------------------------------------------------------------------------- #


def _construct(ctx: _Ctx, order: list[int]) -> _State:
    """Best-fit construction over the fixed slots, splitting to respect capacity.

    Customers are placed in the given ``order``. Each customer is first placed whole in
    the compatible slot with room that minimises the insertion distance; if none has
    room, its demand is split across compatible slots (most-spare-capacity first);
    any residual is dumped into its largest-capacity compatible slot (an overload the
    Tabu Search then repairs). Full demand is always delivered, so demand coverage is
    satisfied by construction.
    """
    S = ctx.n_slots
    st = ctx.slot_type
    routes: list[list[int]] = [[] for _ in range(S)]
    delivs: list[dict[int, int]] = [dict() for _ in range(S)]
    remcap = [ctx.caps[st[s]] for s in range(S)]

    def insert(s: int, c: int, q: int) -> None:
        if c in delivs[s]:
            delivs[s][c] += q
        else:
            pos, _ = _best_insert(ctx.dist, routes[s], c, ctx.depot)
            routes[s] = routes[s][:pos] + [c] + routes[s][pos:]
            delivs[s][c] = q
        remcap[s] -= q

    for c in order:
        need = int(ctx.demands[c])
        comp = [s for s in range(S) if st[s] in ctx.allowed[c]]
        if not comp:  # should never happen (validated), but stay robust
            continue
        # 1) place whole in the cheapest-insertion slot that has room and stays in time.
        best = None
        for s in comp:
            if remcap[s] < need:
                continue
            pos, add = _best_insert(ctx.dist, routes[s], c, ctx.depot)
            if ctx.durs[st[s]] > 0 and not ctx.dur_ok(
                routes[s][:pos] + [c] + routes[s][pos:], st[s]
            ):
                continue
            if best is None or add < best[0]:
                best = (add, s)
        if best is not None:
            insert(best[1], c, need)
            continue
        # 2) split across compatible slots, most spare capacity first.
        for s in sorted(comp, key=lambda s: remcap[s], reverse=True):
            if need <= 0:
                break
            if remcap[s] <= 0:
                continue
            q = min(need, remcap[s])
            if ctx.durs[st[s]] > 0:
                pos, _ = _best_insert(ctx.dist, routes[s], c, ctx.depot)
                if c not in delivs[s] and not ctx.dur_ok(
                    routes[s][:pos] + [c] + routes[s][pos:], st[s]
                ):
                    continue
            insert(s, c, q)
            need -= q
        # 3) residual -> largest-capacity compatible slot (overload; repaired in search).
        if need > 0:
            s = max(comp, key=lambda s: ctx.caps[st[s]])
            insert(s, c, need)

    return _State(ctx, routes, delivs)


def _default_order(ctx: _Ctx) -> list[int]:
    """Most-constrained customers first (fewest allowed types, then largest demand)."""
    return sorted(
        ctx.inst.customers,
        key=lambda c: (len(ctx.allowed[c]), -int(ctx.demands[c])),
    )


def _base_order(ctx: _Ctx, base: Solver, time_budget_s: float, seed: int) -> list[int]:
    """Customer order from a relaxed homogeneous CVRP solved by the base solver.

    Forced (single-allowed-type) customers are still placed first for feasibility; the
    remaining customers follow the base solver's route order, which clusters
    geographically close customers so best-fit tends to co-locate them in a slot.
    """
    inst = ctx.inst
    relaxed = Instance(
        name=f"{inst.name}-relaxed",
        variant=CVRP,
        num_nodes=inst.num_nodes,
        coords=inst.coords,
        demands=inst.demands,
        capacity=int(max(ctx.caps)),
        distance=inst.distance,
        depot=ctx.depot,
        num_vehicles=None,
        max_vehicles=ctx.n_slots,
    )
    init_budget = float(min(15.0, max(1.0, time_budget_s * 0.3)))
    sol = base.solve(relaxed, time_budget_s=init_budget, seed=seed)
    seq = [c for r in sol.routes for c in r if c != ctx.depot]
    forced = [c for c in ctx.inst.customers if len(ctx.allowed[c]) == 1]
    seen = set(forced)
    tail = [c for c in seq if c not in seen]
    seen.update(tail)
    missing = [c for c in ctx.inst.customers if c not in seen]
    return forced + tail + missing


# --------------------------------------------------------------------------- #
# Tabu Search neighbourhood                                                   #
# --------------------------------------------------------------------------- #


def _targets_for(ctx: _Ctx, state: _State, c: int, empty_rep: dict[int, int]) -> list[int]:
    """Compatible target slots for customer ``c``: all non-empty plus one empty per type."""
    targets = []
    for s in range(ctx.n_slots):
        if ctx.slot_type[s] not in ctx.allowed[c]:
            continue
        if state.routes[s] or empty_rep.get(ctx.slot_type[s]) == s:
            targets.append(s)
    return targets


def _candidates(ctx: _Ctx, state: _State, rng: np.random.Generator):
    """Yield (delta, move_key, changes) over Relocate, Swap and Split-Adjust moves."""
    dist = ctx.dist
    routes = state.routes
    nz = [i for i, r in enumerate(routes) if r]
    empty_rep: dict[int, int] = {}
    for s in range(ctx.n_slots):
        if not routes[s]:
            empty_rep.setdefault(ctx.slot_type[s], s)

    # ---- Relocate: move a customer's whole delivery to another slot -------------
    seeds = [(ri, c) for ri in nz for c in routes[ri]]
    if len(seeds) > _MAX_RELOCATE_SEEDS:
        pick = rng.choice(len(seeds), size=_MAX_RELOCATE_SEEDS, replace=False)
        seeds = [seeds[i] for i in pick.tolist()]
    for ri, c in seeds:
        q = state.deliveries[ri][c]
        rl1 = [x for x in routes[ri] if x != c]
        dl1 = {x: state.deliveries[ri][x] for x in rl1}
        for rj in _targets_for(ctx, state, c, empty_rep):
            if rj == ri:
                continue
            if c in state.deliveries[rj]:  # merge a split back together
                dl2 = dict(state.deliveries[rj])
                dl2[c] += q
                changes = {ri: (rl1, dl1), rj: (list(routes[rj]), dl2)}
            else:
                pos, _ = _best_insert(dist, routes[rj], c, ctx.depot)
                rl2 = routes[rj][:pos] + [c] + routes[rj][pos:]
                dl2 = dict(state.deliveries[rj])
                dl2[c] = q
                changes = {ri: (rl1, dl1), rj: (rl2, dl2)}
            yield state.delta(changes), (c, ri, rj), changes

    # ---- Swap: exchange two customers between two non-empty slots ---------------
    if len(seeds) >= 2:
        for _ in range(_MAX_SWAP_TRIES):
            ri, c1 = seeds[int(rng.integers(0, len(seeds)))]
            rj, c2 = seeds[int(rng.integers(0, len(seeds)))]
            if ri == rj or c1 == c2:
                continue
            st_i, st_j = ctx.slot_type[ri], ctx.slot_type[rj]
            if st_i not in ctx.allowed[c2] or st_j not in ctx.allowed[c1]:
                continue
            if c2 in state.deliveries[ri] or c1 in state.deliveries[rj]:
                continue  # avoid a duplicate visit on a slot
            q1, q2 = state.deliveries[ri][c1], state.deliveries[rj][c2]
            base1 = [x for x in routes[ri] if x != c1]
            p1, _ = _best_insert(dist, base1, c2, ctx.depot)
            rl1 = base1[:p1] + [c2] + base1[p1:]
            dl1 = {x: state.deliveries[ri][x] for x in base1}
            dl1[c2] = q2
            base2 = [x for x in routes[rj] if x != c2]
            p2, _ = _best_insert(dist, base2, c1, ctx.depot)
            rl2 = base2[:p2] + [c1] + base2[p2:]
            dl2 = {x: state.deliveries[rj][x] for x in base2}
            dl2[c1] = q1
            changes = {ri: (rl1, dl1), rj: (rl2, dl2)}
            yield state.delta(changes), (c1, ri, rj), changes

    # ---- Split Adjust: shift part of a customer's demand between two slots -------
    splittable = [(ri, c) for ri, c in seeds if state.deliveries[ri][c] > 1]
    if splittable:
        for _ in range(_MAX_SPLIT_TRIES):
            ri, c = splittable[int(rng.integers(0, len(splittable)))]
            targets = [rj for rj in _targets_for(ctx, state, c, empty_rep) if rj != ri]
            if not targets:
                continue
            rj = targets[int(rng.integers(0, len(targets)))]
            q = state.deliveries[ri][c]
            d = q // 2 if q > 1 else 1
            if q - d <= 0:
                rl1 = [x for x in routes[ri] if x != c]
                dl1 = {x: state.deliveries[ri][x] for x in rl1}
            else:
                rl1 = list(routes[ri])
                dl1 = dict(state.deliveries[ri])
                dl1[c] = q - d
            if c in state.deliveries[rj]:
                rl2 = list(routes[rj])
                dl2 = dict(state.deliveries[rj])
                dl2[c] += d
            else:
                pos, _ = _best_insert(dist, routes[rj], c, ctx.depot)
                rl2 = routes[rj][:pos] + [c] + routes[rj][pos:]
                dl2 = dict(state.deliveries[rj])
                dl2[c] = d
            changes = {ri: (rl1, dl1), rj: (rl2, dl2)}
            yield state.delta(changes), (c, ri, rj), changes


class SDVRPSolver:
    """Tabu Search for SDVRP; optionally seeded by a wrapped CVRP base solver."""

    supported_variants = (SDVRP,)

    def __init__(self, base_solver: Solver | None = None) -> None:
        self.base = base_solver
        self.name = "sdvrp_tabu" if base_solver is None else f"sdvrp_{base_solver.name}"

    def version(self) -> str:
        if self.base is None:
            return "sdvrp-tabu"
        return f"sdvrp-tabu+{self.base.version()}"

    def solve(self, instance: Instance, *, time_budget_s: float, seed: int) -> Solution:
        if instance.variant != SDVRP:
            raise SolverError(f"SDVRPSolver does not support {instance.variant!r}")
        if instance.depot != 0:
            raise SolverError("SDVRPSolver assumes depot at index 0")

        start = time.perf_counter()
        rng = np.random.default_rng(seed)
        # Large finite penalty: the sum of all arcs dominates any feasible total
        # distance, so reducing infeasibility always beats any distance gain while the
        # acceptance arithmetic stays finite.
        penalty = float(instance.distance.sum()) + 1.0
        ctx = _Ctx(instance, penalty)

        if not list(instance.customers):
            return Solution(routes=[], objective=0.0, feasible=True,
                            runtime_s=time.perf_counter() - start)

        # --- initial solution --------------------------------------------------
        if self.base is None:
            order = _default_order(ctx)
        else:
            try:
                order = _base_order(ctx, self.base, time_budget_s, seed)
            except SolverError:
                order = _default_order(ctx)  # base failed — fall back
        state = _construct(ctx, order)

        best = state.copy()
        best_cost = best.cost()

        # --- tabu search -------------------------------------------------------
        tabu: deque = deque(maxlen=20)
        no_improve = 0
        no_improve_limit = 100
        deadline = start + time_budget_s

        # The no-improvement early-exit only applies once a feasible solution exists:
        # while still infeasible, feasibility outranks saving time, so keep searching
        # until the wall-clock budget is spent.
        while time.perf_counter() < deadline and not (
            best.is_feasible() and no_improve >= no_improve_limit
        ):
            cur_cost = state.cost()
            best_move = None       # best move that yields a new global best (aspiration)
            best_admissible = None  # best non-tabu move
            for delta, key, changes in _candidates(ctx, state, rng):
                improves_global = cur_cost + delta < best_cost - 1e-9
                if key in tabu and not improves_global:
                    continue
                if best_admissible is None or delta < best_admissible[0]:
                    best_admissible = (delta, key, changes)
                if improves_global and (best_move is None or delta < best_move[0]):
                    best_move = (delta, key, changes)

            chosen = best_move or best_admissible
            if chosen is None:
                break
            delta, key, changes = chosen
            state.apply(changes)
            tabu.append(key)

            if state.cost() < best_cost - 1e-9:
                best_cost = state.cost()
                best = state.copy()
                no_improve = 0
            else:
                no_improve += 1

        return _to_solution(best, time.perf_counter() - start)


def _to_solution(state: _State, runtime_s: float) -> Solution:
    """Rebuild a :class:`Solution` from the non-empty slots; objective is pure distance."""
    ctx = state.ctx
    routes, types, delivs = [], [], []
    for s in range(ctx.n_slots):
        if state.routes[s]:
            routes.append(list(state.routes[s]))
            types.append(ctx.slot_type[s])
            delivs.append(dict(state.deliveries[s]))
    objective = float(sum(_route_distance(ctx.dist, r, ctx.depot) for r in routes))
    return Solution(
        routes=routes,
        objective=objective,
        feasible=state.is_feasible(),
        runtime_s=runtime_s,
        route_vehicle_types=types,
        route_deliveries=delivs,
    )
