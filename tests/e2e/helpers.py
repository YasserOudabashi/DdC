"""
Helper condivisi per i test E2E (Fase 11) — API async di Playwright.

Le città usano TomSelect (create:true): si digita il nome e si preme Invio per
creare la voce; l'NPA si imposta direttamente sull'input nascosto. Lo stub del
geocoder in conftest mappa NPA/città → coordinate fisse, quindi i km sono
deterministici.
"""
from __future__ import annotations

from playwright.async_api import Page, expect


async def set_city(page: Page, field_id: str, city: str) -> None:
    """Imposta una città su un controllo TomSelect (digita + Invio)."""
    control = page.locator(f"#{field_id}-ts-control")
    await control.click()
    await control.type(city)
    await page.keyboard.press("Enter")


async def fill_address(
    page: Page,
    prefix: str,
    *,
    city: str,
    street: str,
    npa: str,
    country: str | None = None,
) -> None:
    """Compila un blocco indirizzo (prefix='home' | 'work')."""
    await set_city(page, f"{prefix}_city", city)
    await page.fill(f"#{prefix}_street", street)
    # L'NPA va impostato DOPO la città (onItemAdd può sovrascriverlo se vuoto).
    await page.fill(f"#{prefix}_npa", npa)
    if country:
        await page.select_option(f"#{prefix}_country", country)


async def fill_minimal_addresses(page: Page) -> None:
    """Indirizzi validi di default: Bellinzona (casa) → Lugano (lavoro), ~30 km."""
    await fill_address(page, "home", city="Bellinzona", street="Viale Stazione 1", npa="6500")
    await fill_address(page, "work", city="Lugano", street="Via Pretorio 1", npa="6900")


async def calcola(page: Page):
    """Invia il form e attende che i risultati IC/IFD siano renderizzati."""
    await page.get_by_role("button", name="Calcola deduzione").click()
    results = page.locator("#results")
    await expect(results).to_be_visible(timeout=10_000)
    # Attende la fine del calcolo: lo spinner viene sostituito dalle colonne IC/IFD.
    await expect(results).to_contain_text("Cantonale TI", timeout=15_000)
    return results


async def results_text(page: Page) -> str:
    return await page.locator("#results").inner_text()
