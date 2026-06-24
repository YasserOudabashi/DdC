"""Unit test per i comportamenti di sicurezza critici: API key, rate limit IP, Address validation."""
from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from pydantic import ValidationError

from app.security import verify_api_key, get_real_ip
from app.schemas.request import Address


# ─── API Key ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_key_empty_allows_all():
    """Se api_key non è configurata, qualsiasi richiesta passa senza errori."""
    with patch("app.security.settings") as mock_settings:
        mock_settings.api_key = ""
        await verify_api_key(api_key=None)


@pytest.mark.asyncio
async def test_api_key_wrong_raises_401():
    """Chiave sbagliata → HTTPException 401."""
    with patch("app.security.settings") as mock_settings:
        mock_settings.api_key = "correct-key"
        with pytest.raises(HTTPException) as exc_info:
            await verify_api_key(api_key="wrong-key")
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_api_key_correct_passes():
    """Chiave corretta → nessuna eccezione."""
    with patch("app.security.settings") as mock_settings:
        mock_settings.api_key = "correct-key"
        await verify_api_key(api_key="correct-key")


# ─── Real IP / Proxy ──────────────────────────────────────────────────────────

def test_get_real_ip_direct():
    """Senza proxy fidati, ritorna sempre client.host."""
    req = MagicMock()
    req.client.host = "5.6.7.8"
    with patch("app.security.settings") as mock_settings:
        mock_settings.trusted_proxies = ""
        ip = get_real_ip(req)
    assert ip == "5.6.7.8"


def test_get_real_ip_from_xfwd():
    """Se client.host è un proxy fidato, legge il primo IP da X-Forwarded-For."""
    req = MagicMock()
    req.client.host = "127.0.0.1"
    req.headers = {"X-Forwarded-For": "9.8.7.6, 127.0.0.1"}
    with patch("app.security.settings") as mock_settings:
        mock_settings.trusted_proxies = "127.0.0.1"
        ip = get_real_ip(req)
    assert ip == "9.8.7.6"


# ─── Address Validation ───────────────────────────────────────────────────────

def test_postal_code_too_long_invalid():
    """postal_code oltre 10 caratteri → ValidationError."""
    with pytest.raises(ValidationError):
        Address(city="Lugano", postal_code="A" * 20, country="CH")


def test_country_too_long_invalid():
    """country con più di 2 caratteri → ValidationError."""
    with pytest.raises(ValidationError):
        Address(city="Lugano", postal_code="6900", country="CHE")
