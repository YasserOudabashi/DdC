"""E2E US-1104: motocicletta targa bianca e bicicletta."""
import pytest
from playwright.async_api import expect

from .helpers import calcola, fill_minimal_addresses, results_text, select_transport

pytestmark = pytest.mark.e2e


async def test_motorcycle_with_distance(live_server, page):
    """Moto targa bianca: mostra il campo distanza e produce risultati IC+IFD."""
    await page.goto(live_server)
    await select_transport(page, "motorcycle")
    await expect(page.locator("#distance-override-group")).to_be_visible()
    await fill_minimal_addresses(page)  # geocodificato ~27 km
    await page.fill("#override_distance_km", "30")

    results = await calcola(page)
    text = await results_text(page)
    assert "Motocicletta" in text
    await expect(results).to_contain_text("Cantonale TI (IC)")
    await expect(results).to_contain_text("Federale IFD")


async def test_bicycle_flat_rate_no_distance(live_server, page):
    """Bicicletta/e-bike: forfait CHF 700 senza richiedere la distanza."""
    await page.goto(live_server)
    await select_transport(page, "bicycle")
    # La bici non richiede il campo distanza.
    await expect(page.locator("#distance-override-group")).to_be_hidden()
    await fill_minimal_addresses(page)

    results = await calcola(page)
    text = await results_text(page)
    assert "Bicicletta" in text
    assert "700.00" in text  # forfait bici CHF 700
    await expect(results).to_contain_text("Cantonale TI (IC)")
    await expect(results).to_contain_text("Federale IFD")
