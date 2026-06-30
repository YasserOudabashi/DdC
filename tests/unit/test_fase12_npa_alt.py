"""
Fase 12 — Validazione NPA + scenario alternativo auto→stazione+abbonamento.
"""
from __future__ import annotations
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.rules.loader import load_rules
from app.core.calculator import estimate_arcobaleno_zones, build_alternative_transport
from app.geo.providers.base import GeoResolved


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _post(payload: dict) -> tuple[int, dict]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/deduction/calculate", json=payload)
    return resp.status_code, resp.json()


CAR_PAYLOAD = {
    "fiscal_year": 2026,
    "home_address": {"street": "Via Test 1", "city": "Lugano", "postal_code": "6900"},
    "work_address": {"street": "Viale Test 2", "city": "Bellinzona", "postal_code": "6500"},
    "transport_mode": "private_car",
    "residency_type": "resident_TI",
    "work_schedule": {"days_per_week": 5, "home_office_days_per_week": 0},
    "include_meals": False,
    "include_other_expenses": False,
}


# ── Stima zone da distanza ──────────────────────────────────────────────────────

def test_estimate_zones_bands():
    rules = load_rules(2026)
    assert estimate_arcobaleno_zones(3, rules) == 1     # ≤5
    assert estimate_arcobaleno_zones(8, rules) == 2     # ≤10
    assert estimate_arcobaleno_zones(15, rules) == 3    # ≤18
    assert estimate_arcobaleno_zones(25, rules) == 4    # ≤28
    assert estimate_arcobaleno_zones(200, rules) == 8   # oltre l'ultima fascia


# ── Costruzione scenario alternativo ────────────────────────────────────────────

def test_build_alternative_transport_values():
    rules = load_rules(2026)
    alt = build_alternative_transport(
        distance_km=20.0, station_distance_km=2.0, effective_days=220, rules=rules,
    )
    assert alt is not None
    cantonal, federal = alt
    # 2 componenti: auto fino alla stazione + abbonamento
    assert len(cantonal.lines) == 2
    assert cantonal.mode == "car_to_station_plus_subscription"
    # Abbonamento = lookup Arcobaleno (zone stimate da 20km → zona 4) classe 2
    zones = estimate_arcobaleno_zones(20.0, rules)
    abbo_expected = rules.cantonal_TI.public_transport_subscriptions.arcobaleno_annual_adult_2cl
    abbo_val = {1: abbo_expected.zones_1, 2: abbo_expected.zones_2, 3: abbo_expected.zones_3,
                4: abbo_expected.zones_4}[zones]
    assert cantonal.lines[1].amount_chf == abbo_val
    # Tratto auto = 0.75 × 2 × 2 × 220
    car_leg = round(0.75 * 2.0 * 2 * 220, 2)
    assert cantonal.lines[0].amount_chf == car_leg
    assert cantonal.net_deduction_chf == round(car_leg + abbo_val, 2)


def test_build_alternative_returns_none_without_station():
    rules = load_rules(2026)
    assert build_alternative_transport(20.0, None, 220, rules) is None
    assert build_alternative_transport(None, 2.0, 220, rules) is None


# ── Validazione NPA (integration) ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_npa_mismatch_warning():
    """NPA inserito 6900 ma risolto 6500 → warning + address_validation matched=False."""
    home_res = GeoResolved(lat=46.0, lon=8.95, postcode="6500", city="Bellinzona")
    work_res = GeoResolved(lat=46.19, lon=9.02, postcode="6500", city="Bellinzona")
    with patch(
        "app.api.v1.endpoints.deduction.resolve_distance",
        new=AsyncMock(return_value=(25.0, "swisstopo", (46.0, 8.95), (46.19, 9.02), home_res, work_res)),
    ), patch(
        "app.geo.tp_proximity.find_nearest_stop", new=AsyncMock(return_value=None),
    ):
        payload = {**CAR_PAYLOAD, "override_distance_km": 25.0}
        status, body = await _post(payload)
    assert status == 200
    checks = body["address_validation"]
    home_check = next(c for c in checks if c["field"] == "home")
    assert home_check["matched"] is False
    assert home_check["resolved_npa"] == "6500"
    assert any("6900" in w and "non corrisponde" in w for w in body["warnings"])


@pytest.mark.asyncio
async def test_npa_match_no_warning():
    home_res = GeoResolved(lat=46.0, lon=8.95, postcode="6900", city="Lugano")
    work_res = GeoResolved(lat=46.19, lon=9.02, postcode="6500", city="Bellinzona")
    with patch(
        "app.api.v1.endpoints.deduction.resolve_distance",
        new=AsyncMock(return_value=(25.0, "swisstopo", (46.0, 8.95), (46.19, 9.02), home_res, work_res)),
    ), patch(
        "app.geo.tp_proximity.find_nearest_stop", new=AsyncMock(return_value=None),
    ):
        payload = {**CAR_PAYLOAD, "override_distance_km": 25.0}
        status, body = await _post(payload)
    assert status == 200
    assert all(c["matched"] for c in body["address_validation"])
    assert not any("non corrisponde" in w for w in body["warnings"])


# ── Scenario alternativo (integration) ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_alternative_scenario_when_car_blocked():
    """Auto privata, distanza <30km → auto bloccata + scenario alternativo presente."""
    with patch(
        "app.api.v1.endpoints.deduction.resolve_distance",
        new=AsyncMock(return_value=(12.0, "swisstopo", (46.0, 8.95), (46.05, 8.97), None, None)),
    ), patch(
        "app.geo.tp_proximity.find_nearest_stop",
        new=AsyncMock(return_value=("Stazione FFS", 800.0)),
    ):
        payload = {**CAR_PAYLOAD, "override_distance_km": None}
        status, body = await _post(payload)
    assert status == 200
    # Auto azzerata
    assert body["cantonal_TI"]["transport_deduction"]["net_deduction_chf"] == 0.0
    # Scenario alternativo presente con 2 componenti
    alt = body["cantonal_TI"]["alternative_transport"]
    assert alt is not None
    assert alt["mode"] == "car_to_station_plus_subscription"
    assert len(alt["lines"]) == 2
    assert alt["net_deduction_chf"] > 0.0
    assert any("Scenario alternativo" in w for w in body["warnings"])
