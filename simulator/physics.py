"""
physics.py
──────────
GPS / movement helper functions used by the Bus simulation loop.

Functions
─────────
haversine_km(p1, p2)  → float
    Great-circle distance between two lat/lon dicts, in kilometres.

lerp_pos(p1, p2, t)   → dict
    Linear interpolation between two GPS points at fractional position t ∈ [0, 1].
"""

import math


def haversine_km(p1: dict, p2: dict) -> float:
    """
    Return the great-circle distance in km between two lat/lon points.

    Parameters
    ----------
    p1, p2 : dict  with keys "lat" and "lon" (degrees)
    """
    R = 6371.0
    lat1, lat2 = math.radians(p1["lat"]), math.radians(p2["lat"])
    dlat = lat2 - lat1
    dlon = math.radians(p2["lon"] - p1["lon"])
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def lerp_pos(p1: dict, p2: dict, t: float) -> dict:
    """
    Linear interpolation between two GPS points.

    pos = p1 + t × (p2 − p1),   t ∈ [0, 1]

    Parameters
    ----------
    p1, p2 : dict  with keys "lat" and "lon"
    t      : float  interpolation factor
    """
    return {
        "lat": round(p1["lat"] + t * (p2["lat"] - p1["lat"]), 6),
        "lon": round(p1["lon"] + t * (p2["lon"] - p1["lon"]), 6),
    }
