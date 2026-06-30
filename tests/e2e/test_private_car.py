"""E2E US-1103: auto privata (blocco <30km, override distanza, warning cap IFD)."""
import pytest
from playwright.async_api import expect

from .helpers import calcola, fill_address, fill_minimal_addresses, results_text, select_transport

pytestmark = pytest.mark.e2e


async def test_distance_field_appears(live_server, page):
    """Selezionando 'Auto privata' compare il campo 'Distanza effettiva (km)'."""
    await page.goto(live_server)
    await expect(page.locator("#distance-override-group")).to_be_hidden()
    await select_transport(page, "private_car")
    await expect(page.locator("#distance-override-group")).to_be_visible()


async def test_short_distance_blocked(live_server, page):
    """Bellinzona->Giubiasco (<30 km): la deduzione auto privata non è ammessa."""
    await page.goto(live_server)
    await select_transport(page, "private_car")
    await fill_address(page, "home", city="Bellinzona", street="Viale Stazione 1", npa="6500")
    await fill_address(page, "work", city="Giubiasco", street="Via Linoleum 1", npa="6512")

    await calcola(page)
    text = await results_text(page)
    assert "non ammessa" in text
    assert "inferiore a 30 km" in text


async def test_override_coherent_shows_car_deduction(live_server, page):
    """Override coerente (entro 5 km dal geocodificato): il calcolo procede con deduzione auto IC+IFD."""
    await page.goto(live_server)
    await select_transport(page, "private_car")
    await fill_minimal_addresses(page)  # Bellinzona->Lugano, geocodificato ~27 km
    await page.fill("#override_distance_km", "28")

    results = await calcola(page)
    await expect(results).to_contain_text("Auto privata")
    await expect(results).to_contain_text("Cantonale TI (IC)")
    await expect(results).to_contain_text("Federale IFD")


async def test_cap_ifd_warning_and_limit(live_server, page):
    """Distanza elevata: warning cap IFD CHF 3'300 e linea IFD limitata (IC senza tetto)."""
    await page.goto(live_server)
    await select_transport(page, "private_car")
    await fill_minimal_addresses(page)
    await page.fill("#override_distance_km", "32")

    results = await calcola(page)
    # getCapIfdWarning mostrato prima del calcolo (resta visibile dopo il render).
    await expect(page.locator("#form-error")).to_contain_text("tetto legale")
    # La linea IFD risulta limitata al tetto.
    await expect(results).to_contain_text("Tetto massimo applicato")


async def test_override_incoherent_validation_error(live_server, page):
    """Override incoerente (>5 km dal geocodificato): errore di validazione, calcolo non procede."""
    await page.goto(live_server)
    await select_transport(page, "private_car")
    await fill_minimal_addresses(page)
    await page.fill("#override_distance_km", "60")  # geocodificato ~27 km -> diff > 5 km

    await page.get_by_role("button", name="Calcola deduzione").click()
    error = page.locator("#form-error")
    await expect(error).to_be_visible()
    await expect(error).to_contain_text("differisce")
    await expect(page.locator("#results")).to_be_hidden()
