"""Best-known-solution (BKS) lookup from a curated local CSV.

The CSV is populated manually from published CVRPLIB X / Solomon / GH tables so
experiments are fully reproducible with no runtime network access. The
``rounding`` column documents the distance convention under which each value was
computed (``int`` for CVRP EUC_2D, ``float`` for Solomon/GH) — kept consistent
with :mod:`vrpbench.datasets.loader`.

CSV columns: ``instance_name, variant, bks_value, rounding, source``
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

DEFAULT_BKS_PATH = Path("data/bks.csv")


class BksTable:
    """Case-insensitive name -> BKS value lookup."""

    def __init__(self, values: dict[str, float]):
        self._values = {k.lower(): v for k, v in values.items()}

    def lookup(self, instance_name: str) -> float | None:
        return self._values.get(instance_name.lower())

    def __len__(self) -> int:
        return len(self._values)

    def __contains__(self, instance_name: str) -> bool:
        return instance_name.lower() in self._values


def load_bks(path: str | os.PathLike = DEFAULT_BKS_PATH) -> BksTable:
    """Load the curated BKS table. Missing file -> empty table (gaps = None)."""
    p = Path(path)
    if not p.exists():
        return BksTable({})

    values: dict[str, float] = {}
    with p.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = (row.get("instance_name") or "").strip()
            raw = (row.get("bks_value") or "").strip()
            if not name or not raw:
                continue
            values[name] = float(raw)
    return BksTable(values)
