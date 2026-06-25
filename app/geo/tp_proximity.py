"""
Controllo prossimità fermata trasporto pubblico — US-904.
Usa transport.opendata.ch per trovare la fermata più vicina a un punto.
"""
from __future__ import annotations
import math
import httpx


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distanza in metri tra due punti geografici (formula di Haversine)."""
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def find_nearest_stop(
    lat: float, lon: float, timeout: float = 3.0
) -> tuple[str, float] | None:
    """
    Ritorna (nome_fermata, distanza_m) oppure None se la chiamata fallisce
    o non ci sono fermate nelle vicinanze.
    """
    url = "https://transport.opendata.ch/v1/locations"
    params = {"x": lon, "y": lat, "type": "station", "limit": 1}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return None

    stations = data.get("stations") or []
    if not stations:
        return None

    station = stations[0]
    coord = station.get("coordinate") or {}
    s_lat = coord.get("y")
    s_lon = coord.get("x")
    name = station.get("name") or "fermata sconosciuta"

    if s_lat is None or s_lon is None:
        return None

    dist_m = _haversine_m(lat, lon, float(s_lat), float(s_lon))
    return name, dist_m
