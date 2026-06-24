"""Verifica che le security headers siano presenti nelle risposte HTTP."""
from __future__ import annotations
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_security_headers_present():
    """GET / → tutte le security header critiche devono essere presenti."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    assert "content-security-policy" in resp.headers
    assert "x-frame-options" in resp.headers
    assert "x-content-type-options" in resp.headers
    assert "strict-transport-security" in resp.headers
    assert "permissions-policy" in resp.headers


@pytest.mark.asyncio
async def test_health_endpoint_responds():
    """GET /v1/health → 200 con status ok (verifica rate limit non blocca il primo request)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
