"""
Test suite Fase 9 — US-905.
Verifica: work_schedule annidato, basis string con HO, meals_basis_text, warning fermata TP.
"""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app

BASE_CAR = {
    "fiscal_year": 2026,
    "home_address": {
        "street": "Via Nassa 10",
        "city": "Lugano",
        "postal_code": "6900",
        "country": "CH",
    },
    "work_address": {
        "street": "Viale Franscini 30",
        "city": "Bellinzona",
        "postal_code": "6500",
        "country": "CH",
    },
    "transport_mode": "private_car",
    "residency_type": "resident_TI",
    "override_distance_km": 20.0,
    "include_meals": False,
    "include_other_expenses": False,
}

async def _post(payload: dict):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/deduction/calculate", json=payload)
    return resp.status_code, resp.json()


@pytest.fixture
def mock_geo_20km():
    """Mock geocoder: 20 km, coerente con override_distance_km=20.0 in BASE_CAR."""
    with patch(
        "app.api.v1.endpoints.deduction.resolve_distance",
        new=AsyncMock(return_value=(20.0, "swisstopo", (46.004, 8.952), (46.195, 9.015))),
    ):
        yield


@pytest.mark.asyncio
async def test_work_schedule_nested_payload_ho1(mock_geo_20km):
    """Con 1 giorno HO effective_working_days deve essere 176 (non 220)."""
    payload = {**BASE_CAR, "work_schedule": {"days_per_week": 5, "home_office_days_per_week": 1}}
    status, body = await _post(payload)
    assert status == 200
    wd = body["cantonal_TI"]["transport_deduction"]["effective_working_days"]
    assert wd == 176, f"Atteso 176, ottenuto {wd}"


@pytest.mark.asyncio
async def test_work_schedule_zero_ho(mock_geo_20km):
    """Con 0 giorni HO effective_working_days deve essere 220."""
    payload = {**BASE_CAR, "work_schedule": {"days_per_week": 5, "home_office_days_per_week": 0}}
    status, body = await _post(payload)
    assert status == 200
    wd = body["cantonal_TI"]["transport_deduction"]["effective_working_days"]
    assert wd == 220, f"Atteso 220, ottenuto {wd}"


@pytest.mark.asyncio
async def test_basis_text_with_ho(mock_geo_20km):
    """Con HO=1 la basis deve contenere il suffisso con 220/5 e 4 gg/sett."""
    payload = {**BASE_CAR, "work_schedule": {"days_per_week": 5, "home_office_days_per_week": 1}}
    status, body = await _post(payload)
    assert status == 200
    basis = body["cantonal_TI"]["transport_deduction"]["lines"][0]["basis"]
    assert "220/5" in basis, f"Atteso '220/5' nella basis: {basis}"
    assert "4 gg/sett" in basis, f"Atteso '4 gg/sett' nella basis: {basis}"


@pytest.mark.asyncio
async def test_basis_text_without_ho(mock_geo_20km):
    """Con HO=0 la basis NON deve contenere il suffisso HO."""
    payload = {**BASE_CAR, "work_schedule": {"days_per_week": 5, "home_office_days_per_week": 0}}
    status, body = await _post(payload)
    assert status == 200
    basis = body["cantonal_TI"]["transport_deduction"]["lines"][0]["basis"]
    assert "sett. in ufficio" not in basis, f"Suffisso HO inatteso nella basis: {basis}"


@pytest.mark.asyncio
async def test_meals_basis_text(mock_geo_20km):
    """Con include_meals=True e HO=1 il meals_basis_text deve mostrare tariffa e 176 giorni."""
    payload = {
        **BASE_CAR,
        "work_schedule": {"days_per_week": 5, "home_office_days_per_week": 1},
        "include_meals": True,
        "meal_situation": "without_cafeteria",
    }
    status, body = await _post(payload)
    assert status == 200
    basis = body["cantonal_TI"].get("meals_basis_text") or ""
    assert "15.00" in basis, f"Attesa tariffa 15.00 in meals_basis_text: {basis}"
    assert "176" in basis, f"Attesi 176 giorni in meals_basis_text: {basis}"


@pytest.mark.asyncio
async def test_tp_warning_stop_within_200m():
    """Fermata a 150m: deduzione auto bloccata e motivo in warnings."""
    payload = {**BASE_CAR, "override_distance_km": None}
    with patch(
        "app.api.v1.endpoints.deduction.resolve_distance",
        new=AsyncMock(return_value=(10.0, "swisstopo", (46.004, 8.952), (46.012, 8.960))),
    ):
        with patch(
            "app.geo.tp_proximity.find_nearest_stop",
            new=AsyncMock(return_value=("Lugano, Piazza Dante", 150.0)),
        ):
            status, body = await _post(payload)
    assert status == 200
    warnings = body.get("warnings") or []
    assert any("150m" in w for w in warnings), f"Atteso warning con '150m': {warnings}"
    # Deduzione azzerata perché TP accessibile
    assert body["cantonal_TI"]["transport_deduction"]["net_deduction_chf"] == 0.0
    assert body["federal_IFD"]["transport_deduction"]["net_deduction_chf"] == 0.0


@pytest.mark.asyncio
async def test_tp_warning_no_stop():
    """Se find_nearest_stop ritorna None, nessun blocco per fermata TP deve essere aggiunto."""
    payload = {**BASE_CAR, "override_distance_km": None}
    with patch(
        "app.api.v1.endpoints.deduction.resolve_distance",
        new=AsyncMock(return_value=(10.0, "swisstopo", (46.004, 8.952), (46.012, 8.960))),
    ):
        with patch(
            "app.geo.tp_proximity.find_nearest_stop",
            new=AsyncMock(return_value=None),
        ):
            status, body = await _post(payload)
    assert status == 200
    warnings = body.get("warnings") or []
    assert not any("Fermata TP" in w for w in warnings), f"Warning TP inatteso: {warnings}"


@pytest.mark.asyncio
async def test_tp_warning_stop_beyond_200m():
    """Fermata a 250m (> 200m): nessun blocco per TP, nessun warning fermata."""
    payload = {**BASE_CAR, "override_distance_km": None}
    with patch(
        "app.api.v1.endpoints.deduction.resolve_distance",
        new=AsyncMock(return_value=(10.0, "swisstopo", (46.004, 8.952), (46.012, 8.960))),
    ):
        with patch(
            "app.geo.tp_proximity.find_nearest_stop",
            new=AsyncMock(return_value=("Stazione", 250.0)),
        ):
            status, body = await _post(payload)
    assert status == 200
    warnings = body.get("warnings") or []
    assert not any("Fermata TP" in w for w in warnings), f"Warning TP inatteso: {warnings}"
