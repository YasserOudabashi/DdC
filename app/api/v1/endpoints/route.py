"""
Percorso casa-lavoro con i mezzi pubblici (US-12xx).

Proxy verso transport.opendata.ch /v1/connections: restituisce una polyline
(elenco di punti lat/lon delle fermate) da disegnare sulla mappa Leaflet, così il
percorso è visibile anche per il trasporto pubblico (OSRM copre solo auto/bici/piedi).
Evita problemi CORS/mixed-content gestendo la chiamata lato server.
"""
from __future__ import annotations
from fastapi import APIRouter, Request
import httpx

from app.security import limiter

router = APIRouter()

_CONNECTIONS_URL = "https://transport.opendata.ch/v1/connections"


def _coord(node: dict | None) -> list[float] | None:
    """Estrae [lat, lon] da una stazione transport.opendata.ch (coordinate x=lat, y=lon)."""
    if not node:
        return None
    station = node.get("station") or node
    coord = (station or {}).get("coordinate") or {}
    lat, lon = coord.get("x"), coord.get("y")
    if lat is None or lon is None:
        return None
    return [float(lat), float(lon)]


@router.get("/route/transit")
@limiter.limit("30/minute")
async def transit_route(
    request: Request,
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float,
) -> dict:
    """Ritorna {polyline: [[lat,lon],...], sections: [...], provider}.

    polyline vuota se l'API non risponde: il frontend ricade su una linea retta.
    """
    params = {
        "from": f"{from_lat},{from_lon}",
        "to": f"{to_lat},{to_lon}",
        "limit": 1,
    }
    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(_CONNECTIONS_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return {"polyline": [], "sections": [], "provider": "transport.opendata.ch"}

    connections = data.get("connections") or []
    if not connections:
        return {"polyline": [], "sections": [], "provider": "transport.opendata.ch"}

    sections = connections[0].get("sections") or []
    polyline: list[list[float]] = []
    section_summary: list[dict] = []

    def _add(point: list[float] | None) -> None:
        if point and (not polyline or polyline[-1] != point):
            polyline.append(point)

    for sec in sections:
        journey = sec.get("journey")
        dep = _coord(sec.get("departure"))
        arr = _coord(sec.get("arrival"))
        if journey and journey.get("passList"):
            for stop in journey["passList"]:
                _add(_coord(stop))
            kind = journey.get("category") or journey.get("name") or "mezzo pubblico"
        else:
            _add(dep)
            _add(arr)
            kind = "a piedi"
        section_summary.append({
            "type": kind,
            "from": (sec.get("departure") or {}).get("station", {}).get("name"),
            "to": (sec.get("arrival") or {}).get("station", {}).get("name"),
        })

    return {
        "polyline": polyline,
        "sections": section_summary,
        "provider": "transport.opendata.ch",
    }
