"""
Geocoder primario: swisstopo api3.geo.admin.ch
Gratuito, nessuna API key, copre tutti gli NPA/PLZ svizzeri.
"""
from __future__ import annotations
import re
from typing import Optional, Tuple
import httpx
from .base import GeoProvider, GeoResolved

_BASE = "https://api3.geo.admin.ch/rest/services/api/SearchServer"

# Estrae "<plz> <città>" da un'etichetta swisstopo (es. "Via Nassa 10 6900 Lugano")
_PLZ_CITY_RE = re.compile(r"\b(\d{4})\b\s+([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’.\- ]*)")
_TAG_RE = re.compile(r"<[^>]+>")


class SwisstopoProvider(GeoProvider):
    name = "swisstopo"

    async def resolve(self, address: str) -> Optional[Tuple[float, float]]:
        detailed = await self.resolve_detailed(address)
        if detailed is None:
            return None
        return detailed.lat, detailed.lon

    async def resolve_detailed(self, address: str) -> Optional[GeoResolved]:
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
                postcode, city = _parse_label(attrs)
                return GeoResolved(lat=float(lat), lon=float(lon), postcode=postcode, city=city)
            except (httpx.HTTPError, KeyError, ValueError):
                return None


def _parse_label(attrs: dict) -> Tuple[Optional[str], Optional[str]]:
    """Estrae (PLZ, città) dall'etichetta risolta da swisstopo."""
    text = attrs.get("detail") or _TAG_RE.sub(" ", attrs.get("label") or "")
    m = _PLZ_CITY_RE.search(text)
    if not m:
        return None, None
    plz = m.group(1)
    city = m.group(2).strip()
    # Rimuove eventuali suffissi cantone/paese (es. "lugano ti ch")
    city = re.split(r"\s+(?:ti|ch|gr|vs|graubünden)\b", city, maxsplit=1)[0].strip()
    return plz, (city.title() if city else None)
