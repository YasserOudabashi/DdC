"""
Geocoder fallback: OSM Nominatim
Gratuito, gestisce indirizzi italiani per i frontalieri.
Rate limit: 1 req/s (uso non commerciale).
"""
from __future__ import annotations
from typing import Optional, Tuple
import httpx
from .base import GeoProvider, GeoResolved
from app.config import settings

_BASE = "https://nominatim.openstreetmap.org/search"


class NominatimProvider(GeoProvider):
    name = "nominatim"

    async def resolve(self, address: str) -> Optional[Tuple[float, float]]:
        detailed = await self.resolve_detailed(address)
        if detailed is None:
            return None
        return detailed.lat, detailed.lon

    async def resolve_detailed(self, address: str) -> Optional[GeoResolved]:
        headers = {"User-Agent": f"DdC-Trasferta-Service/1.0 ({settings.nominatim_contact_email})"}
        params = {
            "q": address,
            "format": "json",
            "addressdetails": "1",
            "limit": 1,
            "countrycodes": "ch,it",
        }
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            try:
                resp = await client.get(_BASE, params=params)
                resp.raise_for_status()
                results = resp.json()
                if not results:
                    return None
                first = results[0]
                addr = first.get("address", {}) or {}
                postcode = addr.get("postcode") or addr.get("postal_code")
                city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("municipality")
                return GeoResolved(
                    lat=float(first["lat"]),
                    lon=float(first["lon"]),
                    postcode=postcode,
                    city=city,
                )
            except (httpx.HTTPError, KeyError, ValueError, IndexError):
                return None
