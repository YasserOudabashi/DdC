"""E2E US-1111: validazioni form e usabilità."""
import pytest
from playwright.async_api import expect

from .helpers import calcola, fill_address, fill_minimal_addresses, select_transport

pytestmark = pytest.mark.e2e


async def test_missing_addresses_error(live_server, page):
    """Invio con indirizzi mancanti: compare #form-error e il calcolo non procede."""
    await page.goto(live_server)
    await page.get_by_role("button", name="Calcola deduzione").click()
    error = page.locator("#form-error")
    await expect(error).to_be_visible()
    await expect(error).to_contain_text("città")
    await expect(page.locator("#results")).to_be_hidden()


async def test_npa_country_cross_check(live_server, page):
    """NPA non svizzero con paese CH genera un errore di validazione."""
    await page.goto(live_server)
    await fill_address(page, "home", city="Bellinzona", street="Viale Stazione 1", npa="6500")
    # Luogo di lavoro: NPA a 5 cifre (CAP italiano) ma paese CH -> incoerente.
    await fill_address(page, "work", city="Como", street="Via Milano 1", npa="22100")
    await page.select_option("#work_country", "CH")

    await page.get_by_role("button", name="Calcola deduzione").click()
    error = page.locator("#form-error")
    await expect(error).to_be_visible()
    await expect(error).to_contain_text("cifre")
    await expect(page.locator("#results")).to_be_hidden()


async def test_conditional_sections_by_transport(live_server, page):
    """Cambiando il mezzo di trasporto compaiono/scompaiono i blocchi corretti."""
    await page.goto(live_server)
    # Default mezzi pubblici.
    await expect(page.locator("#pt-cost-section")).to_be_visible()
    await expect(page.locator("#distance-override-group")).to_be_hidden()
    await expect(page.locator("#mixed-fields")).to_be_hidden()

    await select_transport(page, "private_car")
    await expect(page.locator("#distance-override-group")).to_be_visible()
    await expect(page.locator("#company-car-group")).to_be_visible()
    await expect(page.locator("#pt-cost-section")).to_be_hidden()

    await select_transport(page, "mixed")
    await expect(page.locator("#mixed-fields")).to_be_visible()
    await expect(page.locator("#distance-override-group")).to_be_hidden()


async def test_reset_clears_form(live_server, page):
    """'Azzera' ripulisce il form (città TomSelect comprese), nasconde risultati e mappa."""
    await page.goto(live_server)
    await fill_minimal_addresses(page)
    await calcola(page)
    await expect(page.locator("#results")).to_be_visible()

    await page.get_by_role("button", name="Azzera").click()
    await expect(page.locator("#results")).to_be_hidden()
    await expect(page.locator("#map-section")).to_be_hidden()
    # La città TomSelect del domicilio è stata svuotata.
    await expect(page.locator("#home_city-ts-control .item")).to_have_count(0)


async def test_accessibility_basics(live_server, page):
    """#results ha aria-live='polite' e il tooltip Lohnausweis è raggiungibile via tastiera."""
    await page.goto(live_server)
    await expect(page.locator("#results")).to_have_attribute("aria-live", "polite")
    await expect(page.locator(".tooltip-anchor").first).to_have_attribute("tabindex", "0")
