"""
Test di integrazione per l'endpoint POST /v1/deduction/calculate.
Usa httpx.AsyncClient senza rete esterna (override_distance_km nelle fixture).
"""
import json
import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text())


async def _post(payload: dict) -> dict:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/deduction/calculate", json=payload)
    return resp.status_code, resp.json()


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_public_transport_base():
    payload = json.loads((FIXTURES / "request_base.json").read_text())
    status, body = await _post(payload)
    assert status == 200
    assert body["cantonal_TI"]["transport_deduction"]["net_deduction_chf"] == 1800.0
    # Mezzi pubblici: nessun cap anche a livello IFD
    assert body["federal_IFD"]["transport_deduction"]["net_deduction_chf"] == 1800.0


@pytest.mark.asyncio
async def test_private_car_ifd_cap():
    payload = json.loads((FIXTURES / "request_private_car.json").read_text())
    status, body = await _post(payload)
    assert status == 200
    # 18.5km × 0.75 × 2 × (220 * 4/5) = 18.5 × 0.75 × 2 × 176 = 4884 → cappato a 3300 IFD
    federal_transport = body["federal_IFD"]["transport_deduction"]
    assert federal_transport["net_deduction_chf"] == 3300.0

    # Cantonale: nessun cap → importo maggiore
    cantonal_transport = body["cantonal_TI"]["transport_deduction"]
    assert cantonal_transport["net_deduction_chf"] > 3300.0


@pytest.mark.asyncio
async def test_frontaliero_warning():
    payload = json.loads((FIXTURES / "request_frontaliero.json").read_text())
    status, body = await _post(payload)
    assert status == 200
    warnings = body["warnings"]
    assert any("FRONTALIERE" in w for w in warnings)


@pytest.mark.asyncio
async def test_invalid_fiscal_year():
    payload = json.loads((FIXTURES / "request_base.json").read_text())
    payload["fiscal_year"] = 1999  # anno non disponibile
    status, body = await _post(payload)
    assert status == 422


@pytest.mark.asyncio
async def test_get_rules():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/deduction/rules/2026")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "2026"
    assert data["cantonal_TI"]["transport"]["private_car"]["rate_chf_per_km"] == 0.75


@pytest.mark.asyncio
async def test_mixed_transport_park_and_ride():
    # car_distance_km_mixed: 5.0, public_transport_cost_mixed_chf: 1200.0
    # auto: 0.75 × 5.0 × 2 × 220 = 1650.0; mezzi pubblici: 1200.0; totale: 2850.0
    payload = json.loads((FIXTURES / "request_mixed.json").read_text())
    status, body = await _post(payload)
    assert status == 200
    transport = body["cantonal_TI"]["transport_deduction"]
    assert transport["mode"] == "mixed"
    assert len(transport["lines"]) == 2
    assert transport["net_deduction_chf"] == pytest.approx(2850.0, rel=0.01)


@pytest.mark.asyncio
async def test_weekly_resident():
    # residency_type: weekly_resident, meal_situation: weekly_resident, include_meals: true
    # pasti: CHF 30/giorno × 220 giorni = 6600 → cappato a annual_max_chf 6400
    payload = json.loads((FIXTURES / "request_weekly_resident.json").read_text())
    status, body = await _post(payload)
    assert status == 200
    assert body["cantonal_TI"]["meals_deduction_chf"] == pytest.approx(6400.0, rel=0.01)
    assert any("RESIDENTE SETTIMANALE" in w for w in body["warnings"])


@pytest.mark.asyncio
async def test_other_expenses_without_salary_returns_422():
    # include_other_expenses: true senza annual_net_salary_chf → 422
    payload = json.loads((FIXTURES / "request_base.json").read_text())
    payload["include_other_expenses"] = True
    status, _ = await _post(payload)
    assert status == 422
