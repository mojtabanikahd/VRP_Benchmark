# AGENTS.md - SDVRP R1 Migration Notes

This checkout treats **SDVRP** as the canonical Split Delivery Vehicle Routing Problem using the DIMACS R1 instance corpus in `data/instances/SDVRP_R1_instances/`.

## Dataset

The R1 corpus contains 95 instances in four sets:

- SET-1: `SD*.txt`
- SET-2: `S*D*.sd`
- SET-3: `p*_*.cri`
- SET-4: `eil*.sd`

The file grammar is strict:

```text
n Q
<demand_1> ... <demand_n>
<x_0> <y_0>
...
<x_n> <y_n>
```

The depot is the first coordinate row. Distances are integer-rounded Euclidean using `floor(sqrt(dx^2 + dy^2) + 0.5)`.

## Model

SDVRP R1 is homogeneous split delivery:

- one vehicle capacity `Q`
- integer customer demands
- customers may be served by multiple routes
- per-customer delivered quantities must sum exactly to demand
- no site-dependency, vehicle types, route-duration fields, or hard fleet cap in the instance data

`Solution.route_deliveries` is the authoritative split-delivery detail. `route_vehicle_types` is legacy-only and should not be populated by SDVRP R1 solvers.

## Solvers

Keep the registry names `sdvrp_tabu`, `sdvrp_pyvrp`, `sdvrp_ortools`, and `sdvrp_vroom`. The base-solver variants may use the base solver to seed a homogeneous CVRP-style construction, but final solutions must be evaluated as SDVRP split-delivery solutions with delivery maps.

## Benchmarking

- Smoke config: `experiments/sdvrp_smoke.yaml`, representative instances from all four R1 sets, four solvers, seeds `[0, 1]`, 10 seconds.
- Full config: `experiments/sdvrp_benchmark.yaml`, all 95 R1 instances, four solvers, ten seeds, 10 seconds, 3,800 cells.
- BKS rows are included in `data/bks.csv` for all 95 R1 instances and SDVRP reports should include `gap_pct`.

Do not reintroduce the old `data/instances/SDVRP/` Cordeau site-dependent dataset or its heterogeneous vehicle-type semantics under the `SDVRP` variant.
