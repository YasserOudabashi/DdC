"""Formula Haversine + fattore correzione stradale."""
from __future__ import annotations
import math


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def road_distance_km(lat1: float, lon1: float, lat2: float, lon2: float, factor: float = 1.25) -> float:
    return round(haversine_km(lat1, lon1, lat2, lon2) * factor, 2)
