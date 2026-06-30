"""E2E US-1105: trasporto misto (auto fino alla stazione + abbonamento)."""
import pytest
from playwright.async_api import expect

from .helpers import calcola, fill_minimal_addresses, results_text, select_transport

pytestmark = pytest.mark.e2e


async def test_mixed_fields_appear(live_server, page):
    """Selezionando 'Misto auto + treno' compaiono i campi #mixed-fields."""
    await page.goto(live_server)
    await expect(page.locator("#mixed-fields")).to_be_hidden()
    await select_transport(page, "mixed")
    await expect(page.locator("#mixed-fields")).to_be_visible()


async def test_mixed_sums_car_and_pt(live_server, page):
    """Compilati distanza auto e costo abbonamento, il calcolo somma le due quote."""
    await page.goto(live_server)
    await select_transport(page, "mixed")
    await fill_minimal_addresses(page)
    await page.fill("#car_distance_km_mixed", "8")
    await page.fill("#public_transport_cost_mixed_chf", "1200")

    results = await calcola(page)
    text = await results_text(page)
    assert "Auto (tratto" in text
    assert "Mezzi pubblici (tratto rimanente)" in text
    await expect(results).to_contain_text("Cantonale TI (IC)")
    await expect(results).to_contain_text("Federale IFD")
