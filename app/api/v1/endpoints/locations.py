from fastapi import APIRouter, Request
from typing import Optional
import httpx

from app.security import limiter

router = APIRouter()

_OPENDATA_URL = "https://transport.opendata.ch/v1/locations"


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
