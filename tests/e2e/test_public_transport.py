"""E2E US-1102: mezzi pubblici ARCOBALENO (happy path IC+IFD)."""
import pytest
from playwright.async_api import expect

from .helpers import calcola, fill_minimal_addresses, results_text

pytestmark = pytest.mark.e2e


async def test_arcobaleno_happy_path(live_server, page):
    """Bellinzona->Lugano, ARCOBALENO 3 zone 2a classe: risultati IC+IFD con CHF 1'074."""
    await page.goto(live_server)
    # 'Mezzi pubblici' è il valore di default di #transport_mode.
    await fill_minimal_addresses(page)

    results = await calcola(page)
    await expect(results).to_contain_text("Cantonale TI (IC)")
    await expect(results).to_contain_text("Federale IFD")
    # Il costo ARCOBALENO 3 zone 2a cl. (CHF 1'074) compare nei risultati.
    text = await results_text(page)
    assert "ARCOBALENO" in text
    assert "074.00" in text  # 1'074.00 — separatore migliaia agnostico


async def test_arcobaleno_cost_preview_updates(live_server, page):
    """Cambiando le zone l'anteprima #arcobaleno-cost-preview si aggiorna prima del calcolo."""
    await page.goto(live_server)
    preview = page.locator("#arcobaleno-cost-preview")
    await expect(preview).to_contain_text("074.00")  # default 3 zone = CHF 1'074
    await page.select_option("#arcobaleno_zones", "5")
    await expect(preview).to_contain_text("691.00")  # 5 zone = CHF 1'691
    await page.select_option("#arcobaleno_class", "1")
    await expect(preview).to_contain_text("879.00")  # 5 zone 1a cl = CHF 2'879


async def test_manual_subscription_cost(live_server, page):
    """Opzione 'Inserisci costo abbonamento': il valore manuale è usato nel calcolo."""
    await page.goto(live_server)
    await fill_minimal_addresses(page)
    await page.check("input[name=pt_cost_type][value=manuale]")
    await expect(page.locator("#manual-pt-fields")).to_be_visible()
    await page.fill("#annual_public_transport_cost_chf", "1800")

    results = await calcola(page)
    await expect(results).to_contain_text("Cantonale TI (IC)")
    text = await results_text(page)
    assert "800.00" in text  # 1'800.00
