"""Registry contract for the three supported SDVRP methods."""

from vrpbench.core.instance import SDVRP
from vrpbench.solvers import SOLVERS, get_solver


def test_sdvrp_registry_contains_only_new_methods():
    obsolete = {"sdvrp_tabu", "sdvrp_pyvrp", "sdvrp_ortools", "sdvrp_vroom"}
    expected = {"aasa_pyvrp", "aasa_vroom", "alkaid_sdvrp"}

    assert obsolete.isdisjoint(SOLVERS)
    assert expected <= set(SOLVERS)
    for name in expected:
        assert get_solver(name).supported_variants == (SDVRP,)
    assert get_solver("aasa_pyvrp").base.name == "pyvrp"
    assert get_solver("aasa_vroom").base.name == "vroom"
