"""Fase 12 — endpoint percorso mezzi pubblici /v1/route/transit."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


async def _get(params: dict) -> tuple[int, dict]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/route/transit", params=params)
    return resp.status_code, resp.json()


_MOCK_CONN = {
    "connections": [{
        "sections": [
            {
                "departure": {"station": {"name": "Lugano", "coordinate": {"x": 8.95, "y": 46.0}}},
                "arrival": {"station": {"name": "Bellinzona", "coordinate": {"x": 9.02, "y": 46.19}}},
                "journey": {
                    "category": "RE",
                    "passList": [
                        {"station": {"name": "Lugano", "coordinate": {"x": 8.95, "y": 46.0}}},
                        {"station": {"name": "Cadenazzo", "coordinate": {"x": 8.95, "y": 46.15}}},
                        {"station": {"name": "Bellinzona", "coordinate": {"x": 9.02, "y": 46.19}}},
                    ],
                },
            }
        ]
    }]
}


class _Resp:
    def __init__(self, data): self._data = data
    def raise_for_status(self): pass
    def json(self): return self._data


@pytest.mark.asyncio
async def test_transit_route_polyline():
    with patch("app.api.v1.endpoints.route.httpx.AsyncClient") as mock_client:
        instance = mock_client.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=_Resp(_MOCK_CONN))
        status, body = await _get({
            "from_lat": 46.0, "from_lon": 8.95, "to_lat": 46.19, "to_lon": 9.02,
        })
    assert status == 200
    assert len(body["polyline"]) == 3
    assert body["polyline"][0] == [46.0, 8.95]
    assert body["provider"] == "transport.opendata.ch"


@pytest.mark.asyncio
async def test_transit_route_empty_on_failure():
    with patch("app.api.v1.endpoints.route.httpx.AsyncClient") as mock_client:
        instance = mock_client.return_value.__aenter__.return_value
        instance.get = AsyncMock(side_effect=Exception("network down"))
        status, body = await _get({
            "from_lat": 46.0, "from_lon": 8.95, "to_lat": 46.19, "to_lon": 9.02,
        })
    assert status == 200
    assert body["polyline"] == []
