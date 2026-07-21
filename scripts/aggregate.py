"""Aggregate results/results.csv into results/table_data.json.

For every (instance, solver) cell the runs (10 seeds) are reduced to mean metrics
over the successful (status == "ok") runs, plus a "n_ok/n_total" success string.
Instance names are normalised to a clean form first, because the CSV mixes clean
names and full paths *within the same variant* (a resume artifact) and the two forms
must merge into a single cell before aggregating.

Run: python scripts/aggregate.py
"""

from __future__ import annotations

import json
import os
import re

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CSV_PATH = os.path.join(ROOT, "results", "results.csv")
JSON_PATH = os.path.join(ROOT, "results", "table_data.json")
MDVRP_DIR = os.path.join(ROOT, "data", "instances", "MDVRP")

# Per-variant solver lists (display order) and reported metrics.
VARIANT_SPEC = {
    "CVRP": {
        "solvers": ["pyvrp", "ortools", "vroom", "vrpsolvereasy"],
        "metrics": ["obj", "gap", "time", "nveh", "success"],
        "inst_cols": ["Instance", "Customers (n)", "Vehicles (k)"],
    },
    "VRPTW": {
        "solvers": ["pyvrp", "ortools", "vroom", "vrpsolvereasy"],
        "metrics": ["obj", "time", "nveh", "success"],
        "inst_cols": ["Instance", "Class", "Customers (n)"],
    },
    "MDVRP": {
        "solvers": ["pyvrp", "ortools", "vroom"],
        "metrics": ["obj", "time", "nveh", "success"],
        "inst_cols": ["Instance", "Set", "Customers (n)", "Vehicles (k)", "Depots (h)"],
    },
    "VRPMPD": {
        "solvers": ["pyvrp", "ortools", "vroom"],
        "metrics": ["obj", "time", "nveh", "success"],
        "inst_cols": ["Instance", "Base", "Cap. Variant"],
    },
    "SDVRP": {
        "solvers": ["aasa_pyvrp", "aasa_vroom", "alkaid_sdvrp"],
        "metrics": ["obj", "gap", "time", "nveh", "success"],
        "inst_cols": ["Instance", "Set"],
    },
    "PVRP": {
        "solvers": ["pvrp_pyvrp", "pvrp_ortools", "pvrp_vroom"],
        "metrics": ["obj", "time", "nveh", "success"],
        "inst_cols": ["Instance", "Set"],
    },
}

VARIANT_ORDER = ["CVRP", "VRPTW", "MDVRP", "VRPMPD", "SDVRP", "PVRP"]

# Cordeau capacity-variant ordering for VRPMPD (CMTnnH/Q/T/X/Y).
VRPMPD_SUFFIX_ORDER = ["H", "Q", "T", "X", "Y"]


def clean_name(name: str) -> str:
    """Strip any leading path and a trailing known instance extension."""
    base = os.path.basename(str(name))
    return re.sub(r"\.(vrp|txt|vrpmpd|sd|cri)$", "", base)


def _mean(series, ndigits: int):
    """Rounded mean of a series after dropping NaNs; None if nothing left."""
    clean = series.dropna()
    if len(clean) == 0:
        return None
    return round(float(clean.mean()), ndigits)


# --- per-variant instance-feature extraction + sort key -------------------------

def _features_cvrp(name: str):
    m = re.search(r"X-n(\d+)-k(\d+)", name)
    nodes = int(m.group(1)) if m else None
    k = int(m.group(2)) if m else None
    # The "n" in the X-set name counts all nodes (depot + customers); the depot is
    # not a customer, so the customer count is n - 1 (e.g. X-n101-k25 has 100).
    customers = nodes - 1 if nodes is not None else None
    cols = {"Instance": name, "Customers (n)": customers, "Vehicles (k)": k}
    return cols, (nodes if nodes is not None else 1 << 30, name)


def _features_vrptw(name: str):
    m = re.match(r"^([A-Z]+)(\d)", name)
    cls = (m.group(1) + m.group(2)) if m else name
    cols = {"Instance": name, "Class": cls, "Customers (n)": 100}
    return cols, (name,)


def _features_pset(name: str):
    """SDVRP / PVRP: old (p\\d...) vs new (pr...), sorted by number."""
    is_old = bool(re.match(r"^p\d", name))
    m = re.search(r"(\d+)", name)
    num = int(m.group(1)) if m else 0
    cols = {"Instance": name, "Set": "old" if is_old else "new"}
    return cols, (0 if is_old else 1, num, name)


def _features_sdvrp(name: str):
    if re.match(r"^SD\d+$", name):
        set_name, rank = "SET-1", 1
    elif re.match(r"^S\d+D\d+$", name):
        set_name, rank = "SET-2", 2
    elif re.match(r"^p\d+_", name):
        set_name, rank = "SET-3", 3
    elif name.startswith("eil"):
        set_name, rank = "SET-4", 4
    else:
        set_name, rank = "R1", 9
    nums = tuple(int(x) for x in re.findall(r"\d+", name))
    return {"Instance": name, "Set": set_name}, (rank, nums, name)


def _read_mdvrp_params(name: str, is_old: bool):
    """Parse the Cordeau MDVRP first line `type m n t` -> (m, n, t) as ints.

    m = vehicles per depot, n = customers, t = depots. Returns (None, None, None)
    if the instance file is missing or unparseable.
    """
    path = os.path.join(MDVRP_DIR, "old" if is_old else "new", name + ".txt")
    try:
        with open(path, encoding="utf-8") as fh:
            tokens = fh.readline().split()
        _type, m, n, t = (int(tokens[i]) for i in range(4))
        return m, n, t
    except (OSError, ValueError, IndexError):
        return None, None, None


def _features_mdvrp(name: str):
    """MDVRP: like _features_pset, plus n/k/h read from the instance file."""
    is_old = bool(re.match(r"^p\d", name))
    num_match = re.search(r"(\d+)", name)
    num = int(num_match.group(1)) if num_match else 0
    m, n, t = _read_mdvrp_params(name, is_old)
    cols = {
        "Instance": name,
        "Set": "old" if is_old else "new",
        "Customers (n)": n,
        "Vehicles (k)": m,
        "Depots (h)": t,
    }
    return cols, (0 if is_old else 1, num, name)


def _features_vrpmpd(name: str):
    m = re.match(r"CMT0?(\d+)([A-Z]+)", name)
    if m:
        base_num = int(m.group(1))
        suffix = m.group(2)
        base = f"CMT{base_num:02d}"
    else:
        base_num, suffix, base = 1 << 30, "", name
    suffix_rank = (
        VRPMPD_SUFFIX_ORDER.index(suffix) if suffix in VRPMPD_SUFFIX_ORDER else 99
    )
    cols = {"Instance": name, "Base": base, "Cap. Variant": suffix}
    return cols, (base_num, suffix_rank, name)


FEATURE_FUNCS = {
    "CVRP": _features_cvrp,
    "VRPTW": _features_vrptw,
    "MDVRP": _features_mdvrp,
    "VRPMPD": _features_vrpmpd,
    "SDVRP": _features_sdvrp,
    "PVRP": _features_pset,
}


def build_variant(df: pd.DataFrame, variant: str) -> dict:
    spec = VARIANT_SPEC[variant]
    solvers = spec["solvers"]
    metrics = spec["metrics"]
    feature_func = FEATURE_FUNCS[variant]

    sub = df[df["variant"] == variant].copy()

    rows = []
    for inst, inst_df in sub.groupby("clean", sort=False):
        cols, sort_key = feature_func(inst)
        row = dict(cols)
        row["_sort_key"] = sort_key

        for solver in solvers:
            cell = inst_df[inst_df["solver"] == solver]
            ok = cell[cell["status"] == "ok"]
            n_ok = len(ok)
            n_total = len(cell)

            row[f"{solver}_success"] = f"{n_ok}/{n_total}"
            if "obj" in metrics:
                row[f"{solver}_obj"] = _mean(ok["objective"], 1) if n_ok else None
            if "gap" in metrics:
                row[f"{solver}_gap"] = _mean(ok["gap_pct"], 2) if n_ok else None
            if "time" in metrics:
                row[f"{solver}_time"] = _mean(ok["runtime_s"], 2) if n_ok else None
            if "nveh" in metrics:
                row[f"{solver}_nveh"] = _mean(ok["num_vehicles"], 1) if n_ok else None
        rows.append(row)

    rows.sort(key=lambda r: r["_sort_key"])
    for r in rows:
        del r["_sort_key"]

    return {
        "solvers": solvers,
        "metrics": metrics,
        "inst_cols": spec["inst_cols"],
        "rows": rows,
    }


def main() -> None:
    df = pd.read_csv(CSV_PATH)
    df["clean"] = df["instance_name"].apply(clean_name)

    out = {variant: build_variant(df, variant) for variant in VARIANT_ORDER}

    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        # allow_nan=False makes any stray NaN fail loudly instead of writing
        # invalid JSON; every metric is already coerced to a float or None.
        json.dump(out, fh, indent=2, allow_nan=False)

    total_rows = sum(len(v["rows"]) for v in out.values())
    print(f"Wrote {JSON_PATH}")
    for variant in VARIANT_ORDER:
        print(f"  {variant}: {len(out[variant]['rows'])} instances")
    print(f"  total instance rows: {total_rows}")


if __name__ == "__main__":
    main()
