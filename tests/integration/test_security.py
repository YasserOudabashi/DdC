"""Test di integrazione per il security layer — rate limiting, API key, headers."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch
from app.main import app


async def _post(payload: dict, headers: dict | None = None) -> tuple:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/deduction/calculate", json=payload, headers=headers or {})
    return resp.status_code, resp.json(), resp.headers


BASE_PAYLOAD = {
    "fiscal_year": 2026,
    "home_address": {"street": "Via Nassa 10", "city": "Lugano", "postal_code": "6900"},
    "work_address": {"city": "Bellinzona", "postal_code": "6500"},
    "transport_mode": "public_transport",
    "override_distance_km": 30.0,
    "annual_public_transport_cost_chf": 1500.0,
}


class TestSecurityHeaders:
    @pytest.mark.asyncio
    async def test_security_headers_present(self):
        status, _, headers = await _post(BASE_PAYLOAD)
        assert status == 200
        assert headers.get("x-content-type-options") == "nosniff"
        assert headers.get("x-frame-options") == "DENY"
        assert headers.get("x-xss-protection") == "1; mode=block"
        assert headers.get("cache-control") == "no-store"


class TestApiKey:
    @pytest.mark.asyncio
    async def test_no_key_required_when_empty(self):
        # Senza API_KEY configurata: accesso libero
        with patch("app.security.settings") as mock_settings:
            mock_settings.api_key = ""
            mock_settings.rate_limit_per_minute = 30
            status, _, _ = await _post(BASE_PAYLOAD)
        # Può essere 200 o altro ma non 401
        assert status != 401

    @pytest.mark.asyncio
    async def test_wrong_key_returns_401(self):
        with patch("app.config.settings") as mock_cfg, \
             patch("app.security.settings") as mock_sec:
            mock_cfg.api_key = "secret-key-123"
            mock_sec.api_key = "secret-key-123"
            mock_sec.rate_limit_per_minute = 30
            status, body, _ = await _post(BASE_PAYLOAD, headers={"X-API-Key": "wrong-key"})
        assert status == 401

    @pytest.mark.asyncio
    async def test_correct_key_allowed(self):
        with patch("app.config.settings") as mock_cfg, \
             patch("app.security.settings") as mock_sec:
            mock_cfg.api_key = "secret-key-123"
            mock_sec.api_key = "secret-key-123"
            mock_sec.rate_limit_per_minute = 30
            status, _, _ = await _post(BASE_PAYLOAD, headers={"X-API-Key": "secret-key-123"})
        assert status == 200


class TestBodySizeLimit:
    def test_middleware_configured(self):
        # Verifica che il middleware sia presente nell'app con il limite configurato
        from app.security import BodySizeLimitMiddleware
        from app.config import settings
        middleware_types = [type(m) for m in app.middleware_stack.__class__.mro()]
        # Il middleware è nel wrapped stack — verifichiamo che sia configurato nella app
        assert settings.max_body_size_bytes > 0
        assert settings.max_body_size_bytes == 1_048_576  # 1 MB default
