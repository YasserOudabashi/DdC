"""E2E US-1108: coniuge / partner registrato."""
import pytest
from playwright.async_api import expect

from .helpers import calcola, fill_minimal_addresses, results_text

pytestmark = pytest.mark.e2e


async def _fill_spouse_work(page):
    # Mezzi pubblici per il coniuge: nessun vincolo di distanza/override col geocoding.
    await page.select_option("#sp_transport_mode", "public_transport")
    await page.fill("#sp_work_city", "Lugano")
    await page.fill("#sp_work_street", "Via Pretorio 5")
    await page.fill("#sp_work_npa", "6900")


async def test_spouse_section_appears(live_server, page):
    """Spuntando 'Includi coniuge/partner registrato' compare #spouse-fields."""
    await page.goto(live_server)
    await expect(page.locator("#spouse-fields")).to_be_hidden()
    await page.check("#include_spouse")
    await expect(page.locator("#spouse-fields")).to_be_visible()


async def test_same_home_uses_main_domicile(live_server, page):
    """'Stesso domicilio' attivo: campi domicilio coniuge nascosti, calcolo con colonne coniuge."""
    await page.goto(live_server)
    await fill_minimal_addresses(page)
    await page.check("#include_spouse")
    # sp_same_home è spuntato di default -> i campi domicilio coniuge restano nascosti.
    await expect(page.locator("#sp_same_home")).to_be_checked()
    await expect(page.locator("#sp-home-fields")).to_be_hidden()
    await _fill_spouse_work(page)

    await calcola(page)
    text = await results_text(page)
    assert "Coniuge" in text  # colonne dedicate al coniuge (IC/IFD — Coniuge)


async def test_different_home_shows_fields(live_server, page):
    """Deselezionando 'Stesso domicilio' compaiono i campi domicilio coniuge ed è compilabile."""
    await page.goto(live_server)
    await fill_minimal_addresses(page)
    await page.check("#include_spouse")
    await page.uncheck("#sp_same_home")
    await expect(page.locator("#sp-home-fields")).to_be_visible()

    await page.fill("#sp_home_city", "Locarno")
    await page.fill("#sp_home_street", "Piazza Grande 1")
    await page.fill("#sp_home_npa", "6600")
    await expect(page.locator("#sp_home_city")).to_have_value("Locarno")
    await _fill_spouse_work(page)

    results = await calcola(page)
    await expect(results).to_contain_text("Coniuge")
