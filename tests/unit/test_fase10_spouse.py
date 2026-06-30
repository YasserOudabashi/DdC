"""Test suite Fase 10 — coordinate in response e calcolo coniuge/partner."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app

BASE_PAYLOAD = {
    "fiscal_year": 2026,
    "home_address": {"street": "Via Nassa 10", "city": "Lugano", "postal_code": "6900"},
    "work_address": {"street": "Viale Franscini 30", "city": "Bellinzona", "postal_code": "6500"},
    "transport_mode": "public_transport",
    "residency_type": "resident_TI",
    "work_schedule": {"days_per_week": 5, "home_office_days_per_week": 0},
    "arcobaleno_zones": 3,
    "arcobaleno_class": "2",
    "include_meals": False,
    "include_other_expenses": False,
}

MOCK_HOME_COORDS = (46.0037, 8.9511)   # Lugano
MOCK_WORK_COORDS = (46.1954, 9.0228)   # Bellinzona
MOCK_KM = 25.0


@pytest.fixture
def mock_resolve():
    with patch(
        "app.api.v1.endpoints.deduction.resolve_distance",
        new_callable=AsyncMock,
        return_value=(MOCK_KM, "swisstopo", MOCK_HOME_COORDS, MOCK_WORK_COORDS, None, None),
    ) as m:
        yield m


@pytest.fixture
def mock_resolve_fail():
    with patch(
        "app.api.v1.endpoints.deduction.resolve_distance",
        new_callable=AsyncMock,
        return_value=(None, "none", None, None, None, None),
    ) as m:
        yield m


@pytest.fixture
def mock_tp():
    with patch(
        "app.api.v1.endpoints.deduction.tp_proximity.find_nearest_stop",
        new_callable=AsyncMock,
        return_value=None,
    ):
        yield


async def _post(payload: dict) -> dict:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/deduction/calculate", json=payload)
        assert resp.status_code == 200, resp.text
        return resp.json()


# ── US-1001: coordinate nella response ────────────────────────────────────────

@pytest.mark.asyncio
async def test_coordinates_in_response(mock_resolve, mock_tp):
    data = await _post(BASE_PAYLOAD)
    assert data["home_coordinates"] is not None
    assert abs(data["home_coordinates"]["lat"] - MOCK_HOME_COORDS[0]) < 0.001
    assert abs(data["home_coordinates"]["lon"] - MOCK_HOME_COORDS[1]) < 0.001
    assert data["work_coordinates"] is not None
    assert abs(data["work_coordinates"]["lat"] - MOCK_WORK_COORDS[0]) < 0.001
    assert abs(data["work_coordinates"]["lon"] - MOCK_WORK_COORDS[1]) < 0.001


@pytest.mark.asyncio
async def test_coordinates_none_if_geocoding_fails(mock_resolve_fail):
    # override_distance_km serve perché senza geocoding le TP non possono calcolare
    payload = {**BASE_PAYLOAD, "transport_mode": "public_transport", "override_distance_km": 20.0,
               "arcobaleno_zones": 3}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/deduction/calculate", json=payload)
        assert resp.status_code == 200, resp.text
        data = resp.json()
    assert data["home_coordinates"] is None
    assert data["work_coordinates"] is None


# ── US-1002/1003: coniuge assente ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_spouse_none_response(mock_resolve, mock_tp):
    data = await _post(BASE_PAYLOAD)
    assert data["spouse"] is None


# ── US-1003: calcolo coniuge presente ─────────────────────────────────────────

SPOUSE_PAYLOAD = {
    **BASE_PAYLOAD,
    "spouse": {
        "work_address": {"street": "Via Lugano 1", "city": "Locarno", "postal_code": "6600"},
        "transport_mode": "private_car",
        "override_distance_km": 30.0,
        "work_schedule": {"days_per_week": 5, "home_office_days_per_week": 0},
    },
}


@pytest.mark.asyncio
async def test_spouse_independent_calculation(mock_resolve, mock_tp):
    data = await _post(SPOUSE_PAYLOAD)
    assert data["spouse"] is not None
    assert data["spouse"]["cantonal_TI"]["total_deduction_chf"] > 0
    assert data["spouse"]["federal_IFD"]["total_deduction_chf"] > 0


@pytest.mark.asyncio
async def test_spouse_same_home_no_error(mock_resolve, mock_tp):
    """Coniuge senza home_address — usa il domicilio del contribuente, nessun errore."""
    payload = {
        **BASE_PAYLOAD,
        "spouse": {
            "work_address": {"street": "Via Test 1", "city": "Locarno", "postal_code": "6600"},
            "transport_mode": "bicycle",
            # entro i 5 km dalla distanza geocodificata mock (25 km), come per il contribuente
            "override_distance_km": 25.0,
        },
    }
    data = await _post(payload)
    assert data["spouse"] is not None


@pytest.mark.asyncio
async def test_spouse_override_too_far_rejected(mock_resolve, mock_tp):
    """La distanza manuale del coniuge non può discostarsi >5 km dal geocoding (come il contribuente)."""
    payload = {
        **BASE_PAYLOAD,
        "spouse": {
            "work_address": {"street": "Via Test 1", "city": "Locarno", "postal_code": "6600"},
            "transport_mode": "private_car",
            "override_distance_km": 100.0,  # mock geocodificato = 25 km → differenza 75 km
        },
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/deduction/calculate", json=payload)
    assert resp.status_code == 422
    assert "Coniuge" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_spouse_arcobaleno(mock_resolve, mock_tp):
    """Coniuge con ARCOBALENO 3 zone → net == 1074.0."""
    payload = {
        **BASE_PAYLOAD,
        "spouse": {
            "work_address": {"street": "Viale Franscini 30", "city": "Bellinzona", "postal_code": "6500"},
            "transport_mode": "public_transport",
            "arcobaleno_zones": 3,
            "arcobaleno_class": "2",
        },
    }
    data = await _post(payload)
    assert data["spouse"] is not None
    assert data["spouse"]["cantonal_TI"]["transport_deduction"]["net_deduction_chf"] == 1074.0
