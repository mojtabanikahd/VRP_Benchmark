"""Integer scales when VRPTW travel time is not the same quantity as distance.

Solomon instances use one scale because travel time equals distance. A fueling
scenario stores road kilometers on ``distance`` and road minutes on
``travel_times``, so the cost matrix and the clock are scaled separately.
"""

from __future__ import annotations

import numpy as np

from vrpbench.core.instance import VRPTW, Instance

# Kilometers to meters, and minutes to tenths of a minute (the VRPTW scale).
ROAD_DISTANCE_SCALE = 1000
ROAD_TIME_SCALE = 10


def scaled_vrptw(
    instance: Instance, fallback_scale: int
) -> tuple[np.ndarray, np.ndarray, int, int]:
    """Return ``(distance_int, duration_int, distance_scale, time_scale)``.

    ``duration_int`` is what the time window uses. ``distance_int`` is the
    objective. When ``travel_times`` is absent the two matrices match and both
    use ``fallback_scale``, which is the historical Solomon behavior.
    """
    if instance.variant != VRPTW:
        raise ValueError("scaled_vrptw is for VRPTW instances")
    if instance.travel_times is None:
        dist_int = np.rint(instance.distance * fallback_scale).astype(np.int64)
        return dist_int, dist_int.copy(), fallback_scale, fallback_scale
    dist_int = np.rint(instance.distance * ROAD_DISTANCE_SCALE).astype(np.int64)
    duration_int = np.rint(instance.travel_times * ROAD_TIME_SCALE).astype(np.int64)
    return dist_int, duration_int, ROAD_DISTANCE_SCALE, ROAD_TIME_SCALE
