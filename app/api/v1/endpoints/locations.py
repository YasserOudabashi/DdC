from fastapi import APIRouter, Request
from typing import Optional
import re
import httpx

from app.security import limiter
from app.config import settings

router = APIRouter()

_GEO_ADMIN_URL = "https://api3.geo.admin.ch/rest/services/api/SearchServer"
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

_COUNTRY_CODES = {"CH": "ch", "IT": "it", "DE": "de", "FR": "fr", "AT": "at"}


@router.get("/search")
@limiter.limit("60/minute")
async def search_locations(
    request: Request,
    q: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """Cerca località svizzere per nome, restituisce {name, npa} con tutti gli NPA CH."""
    if not q or len(q) < 2:
        return []
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                _GEO_ADMIN_URL,
                params={
                    "type": "locations",
                    "searchText": q,
                    "origins": "zipcode",
                    "limit": str(limit),
                    "returnGeometry": "false",
                    "lang": "it",
                },
            )
            data = resp.json()
    except Exception:
        return []
    results = []
    seen: set[str] = set()
    for result in data.get("results", []):
        attrs = result.get("attrs", {})
        # label format: "<b>6900</b> Lugano"
        label = attrs.get("label", "")
        clean = re.sub(r"<[^>]+>", "", label).strip()
        parts = clean.split(" ", 1)
        if len(parts) == 2:
            npa, city = parts[0], parts[1].strip()
            key = f"{npa}|{city}"
            if key not in seen:
                seen.add(key)
                results.append({"name": city, "npa": npa})
    return results


@router.get("/npa")
@limiter.limit("30/minute")
async def lookup_npa(
    request: Request,
    city: Optional[str] = None,
    country: str = "CH",
) -> dict:
    if not city or len(city) < 2:
        return {"npa": None}
    if country.upper() == "CH":
        npa = await _lookup_npa_ch(city)
        if npa:
            return {"npa": npa}
    # Fallback Nominatim per tutti i paesi
    cc = _COUNTRY_CODES.get(country.upper(), country.lower())
    npa = await _lookup_npa_nominatim(city, cc)
    return {"npa": npa}


async def _lookup_npa_ch(city: str) -> Optional[str]:
    """geo.admin.ch SearchServer — estrae NPA dal campo detail (origins=address)."""
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(
                _GEO_ADMIN_URL,
                params={
                    "type": "locations",
                    "searchText": city,
                    "origins": "address",
                    "limit": "1",
                    "returnGeometry": "false",
                    "lang": "it",
                },
            )
            data = resp.json()
    except Exception:
        return None
    for result in data.get("results", []):
        detail = result.get("attrs", {}).get("detail", "")
        m = re.search(r"#\s*(\d{4})", detail)
        if m:
            return m.group(1)
    return None


async def _lookup_npa_nominatim(city: str, countrycode: str) -> Optional[str]:
    """Nominatim fallback per paesi non CH."""
    headers = {"User-Agent": f"DdC-Trasferta-Service/1.0 ({settings.nominatim_contact_email})"}
    try:
        async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
            resp = await client.get(
                _NOMINATIM_URL,
                params={
                    "q": city, "countrycodes": countrycode,
                    "format": "json", "addressdetails": "1", "limit": "1",
                },
            )
            results = resp.json()
    except Exception:
        return None
    if not results:
        return None
    addr = results[0].get("address", {})
    return addr.get("postcode") or addr.get("postal_code")
