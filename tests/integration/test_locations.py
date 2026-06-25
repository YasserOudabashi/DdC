"""Test integrazione endpoint /v1/locations/search."""
from __future__ import annotations
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_locations_search_short_query():
    """GET /v1/locations/search?q=L → HTTP 200 con [] (q troppo corta)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/locations/search", params={"q": "L"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_locations_search_no_query():
    """GET /v1/locations/search (senza q) → HTTP 200 con []."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/locations/search")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_locations_search_valid_query():
    """GET /v1/locations/search?q=Lugano → HTTP 200, lista (può essere vuota se rete non disponibile)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/locations/search", params={"q": "Lugano"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
