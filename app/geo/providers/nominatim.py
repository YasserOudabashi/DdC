"""
Geocoder fallback: OSM Nominatim
Gratuito, gestisce indirizzi italiani per i frontalieri.
Rate limit: 1 req/s (uso non commerciale).
"""
from __future__ import annotations
from typing import Optional, Tuple
import httpx
from .base import GeoProvider

_BASE = "https://nominatim.openstreetmap.org/search"
_HEADERS = {"User-Agent": "DdC-Trasferta-Service/1.0 (oudabashiy@gmail.com)"}


class NominatimProvider(GeoProvider):
    name = "nominatim"

    async def resolve(self, address: str) -> Optional[Tuple[float, float]]:
        params = {
            "q": address,
            "format": "json",
            "limit": 1,
            "countrycodes": "ch,it",
        }
        async with httpx.AsyncClient(timeout=10.0, headers=_HEADERS) as client:
            try:
                resp = await client.get(_BASE, params=params)
                resp.raise_for_status()
                results = resp.json()
                if not results:
                    return None
                return float(results[0]["lat"]), float(results[0]["lon"])
            except (httpx.HTTPError, KeyError, ValueError, IndexError):
                return None
