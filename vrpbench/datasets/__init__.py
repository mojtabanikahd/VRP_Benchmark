"""Dataset loading and best-known-solution lookup."""

from vrpbench.datasets.bks import BksTable, load_bks
from vrpbench.datasets.loader import load

__all__ = ["load", "BksTable", "load_bks"]
