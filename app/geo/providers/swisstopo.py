"""
Geocoder primario: swisstopo api3.geo.admin.ch
Gratuito, nessuna API key, copre tutti gli NPA/PLZ svizzeri.
"""
from __future__ import annotations
from typing import Optional, Tuple
import httpx
from .base import GeoProvider

_BASE = "https://api3.geo.admin.ch/rest/services/api/SearchServer"


class SwisstopoProvider(GeoProvider):
    name = "swisstopo"

    async def resolve(self, address: str) -> Optional[Tuple[float, float]]:
        params = {
            "searchText": address,
            "type": "locations",
            "limit": 1,
            "sr": "4326",           # WGS84
            "lang": "it",
        }
        async with httpx.AsyncClient(timeout=8.0) as client:
            try:
                resp = await client.get(_BASE, params=params)
                resp.raise_for_status()
                data = resp.json()
                results = data.get("results", [])
                if not results:
                    return None
                attrs = results[0].get("attrs", {})
                lat = attrs.get("lat")
                lon = attrs.get("lon")
                if lat is None or lon is None:
                    return None
                return float(lat), float(lon)
            except (httpx.HTTPError, KeyError, ValueError):
                return None
