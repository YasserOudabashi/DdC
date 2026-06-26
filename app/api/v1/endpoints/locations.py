from fastapi import APIRouter, Request
from typing import Optional
import httpx

from app.security import limiter
from app.config import settings

router = APIRouter()

_OPENPLZ_URL = "https://openplzapi.org/ch/Localities"
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
    """Cerca tutte le località svizzere per nome (openplzapi.org), restituisce {name, npa}."""
    if not q or len(q) < 2:
        return []
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                _OPENPLZ_URL,
                params={"name": q, "limit": str(limit)},
            )
            data = resp.json()
    except Exception:
        return []
    seen: set[str] = set()
    results = []
    for item in (data if isinstance(data, list) else []):
        name = item.get("name", "")
        npa = item.get("postalCode", "")
        if name and npa:
            key = f"{npa}|{name}"
            if key not in seen:
                seen.add(key)
                results.append({"name": name, "npa": npa})
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
    """openplzapi.org — cerca NPA per nome località svizzera."""
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(_OPENPLZ_URL, params={"name": city, "limit": "1"})
            data = resp.json()
    except Exception:
        return None
    if isinstance(data, list) and data:
        return data[0].get("postalCode")
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
