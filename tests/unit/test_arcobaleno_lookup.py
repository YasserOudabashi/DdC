"""Test unitari per il lookup ARCOBALENO nel calculator."""
from __future__ import annotations
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

BASE_PAYLOAD = {
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
    "transport_mode": "public_transport",
    "residency_type": "resident_TI",
    "work_schedule": {"days_per_week": 5.0, "home_office_days_per_week": 0.0},
    "meal_situation": "home",
    "override_distance_km": None,
    "include_meals": False,
    "include_other_expenses": False,
}


async def _post(payload: dict):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/deduction/calculate", json=payload)
    return resp.status_code, resp.json()


@pytest.mark.asyncio
async def test_arcobaleno_2cl_zones_1():
    payload = {**BASE_PAYLOAD, "arcobaleno_zones": 1, "arcobaleno_class": "2"}
    status, body = await _post(payload)
    assert status == 200
    assert body["cantonal_TI"]["transport_deduction"]["net_deduction_chf"] == 485.0


@pytest.mark.asyncio
async def test_arcobaleno_2cl_zones_3():
    payload = {**BASE_PAYLOAD, "arcobaleno_zones": 3, "arcobaleno_class": "2"}
    status, body = await _post(payload)
    assert status == 200
    assert body["cantonal_TI"]["transport_deduction"]["net_deduction_chf"] == 1074.0


@pytest.mark.asyncio
async def test_arcobaleno_2cl_zones_8():
    payload = {**BASE_PAYLOAD, "arcobaleno_zones": 8, "arcobaleno_class": "2"}
    status, body = await _post(payload)
    assert status == 200
    assert body["cantonal_TI"]["transport_deduction"]["net_deduction_chf"] == 2252.0


@pytest.mark.asyncio
async def test_arcobaleno_1cl_zones_2():
    payload = {**BASE_PAYLOAD, "arcobaleno_zones": 2, "arcobaleno_class": "1"}
    status, body = await _post(payload)
    assert status == 200
    assert body["cantonal_TI"]["transport_deduction"]["net_deduction_chf"] == 1245.0


@pytest.mark.asyncio
async def test_arcobaleno_federal_no_cap():
    """Mezzi pubblici non soggetti a cap IFD — zones=3, 2cl → net IFD == 1074."""
    payload = {**BASE_PAYLOAD, "arcobaleno_zones": 3, "arcobaleno_class": "2"}
    status, body = await _post(payload)
    assert status == 200
    assert body["federal_IFD"]["transport_deduction"]["net_deduction_chf"] == 1074.0


@pytest.mark.asyncio
async def test_arcobaleno_federal_no_cap_large():
    """zones=8, 1cl → CHF 3829 — sopra il cap IFD 3300 ma MP non cappato."""
    payload = {**BASE_PAYLOAD, "arcobaleno_zones": 8, "arcobaleno_class": "1"}
    status, body = await _post(payload)
    assert status == 200
    assert body["federal_IFD"]["transport_deduction"]["net_deduction_chf"] == 3829.0


@pytest.mark.asyncio
async def test_arcobaleno_basis_string():
    """La stringa basis deve contenere 'ARCOBALENO' e '1074'."""
    payload = {**BASE_PAYLOAD, "arcobaleno_zones": 3, "arcobaleno_class": "2"}
    status, body = await _post(payload)
    assert status == 200
    lines = body["cantonal_TI"]["transport_deduction"]["lines"]
    basis = lines[0]["basis"]
    assert "ARCOBALENO" in basis
    assert "1074" in basis


@pytest.mark.asyncio
async def test_arcobaleno_invalid_with_private_car():
    """arcobaleno_zones con private_car → HTTP 422."""
    payload = {
        **BASE_PAYLOAD,
        "transport_mode": "private_car",
        "arcobaleno_zones": 3,
        "override_distance_km": 10.0,
    }
    status, _ = await _post(payload)
    assert status == 422


@pytest.mark.asyncio
async def test_arcobaleno_zones_none_fallback():
    """arcobaleno_zones=None + annual_public_transport_cost_chf=1800 → net == 1800 (fallback)."""
    payload = {**BASE_PAYLOAD, "annual_public_transport_cost_chf": 1800.0}
    status, body = await _post(payload)
    assert status == 200
    assert body["cantonal_TI"]["transport_deduction"]["net_deduction_chf"] == 1800.0
