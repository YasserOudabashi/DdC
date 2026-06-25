from fastapi import APIRouter, Request
from typing import Optional
import httpx

from app.security import limiter
from app.config import settings

router = APIRouter()

_OPENDATA_URL = "https://transport.opendata.ch/v1/locations"
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

_COUNTRY_CODES = {"CH": "ch", "IT": "it", "DE": "de", "FR": "fr", "AT": "at"}


@router.get("/search")
@limiter.limit("60/minute")
async def search_locations(
    request: Request,
    q: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    if not q or len(q) < 2:
        return []
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                _OPENDATA_URL,
                params={"query": q, "type": "station", "limit": limit},
            )
            data = resp.json()
    except Exception:
        return []
    stations = data.get("stations", []) or []
    return [
        {"name": s["name"], "id": str(s.get("id", ""))}
        for s in stations
        if s.get("name")
    ]


@router.get("/npa")
@limiter.limit("30/minute")
async def lookup_npa(
    request: Request,
    city: Optional[str] = None,
    country: str = "CH",
) -> dict:
    if not city or len(city) < 2:
        return {"npa": None}
    cc = _COUNTRY_CODES.get(country.upper(), "ch")
    headers = {"User-Agent": f"DdC-Trasferta-Service/1.0 ({settings.nominatim_contact_email})"}
    try:
        async with httpx.AsyncClient(timeout=4.0, headers=headers) as client:
            resp = await client.get(
                _NOMINATIM_URL,
                params={"q": city, "countrycodes": cc, "format": "json", "addressdetails": "1", "limit": "1"},
            )
            results = resp.json()
    except Exception:
        return {"npa": None}
    if not results:
        return {"npa": None}
    postcode = results[0].get("address", {}).get("postcode")
    return {"npa": postcode}
