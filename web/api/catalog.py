"""Solver catalog limited to the studio variants."""

from vrpbench.solvers import SOLVERS, get_solver

from web.api.scenario import STUDIO_VARIANTS


def build_catalog() -> dict:
    """Return studio variants and the solvers that declare each one.

    Solvers outside the studio allow-list, including every PVRP wrapper, are omitted.
    ``version()`` runs only for a solver that actually appears in the catalog, so a
    missing optional engine (for example Alkaid) cannot break the listing.
    """
    matched: dict[str, object] = {}
    for name in SOLVERS:
        solver = get_solver(name)
        if any(variant in solver.supported_variants for variant in STUDIO_VARIANTS):
            matched[name] = solver

    variants = []
    for variant in STUDIO_VARIANTS:
        solvers = []
        for name, solver in matched.items():
            if variant in solver.supported_variants:
                solvers.append({"name": name, "version": solver.version()})
        variants.append({"variant": variant, "solvers": solvers})
    return {"variants": variants}
