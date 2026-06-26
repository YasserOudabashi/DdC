"""Smoke test E2E (Fase 11 US-1101): la homepage carica e il form è presente."""
import pytest
from playwright.async_api import expect

pytestmark = pytest.mark.e2e


async def test_homepage_loads(live_server, page):
    await page.goto(live_server)
    assert "Deduzioni Trasferta" in await page.title()
    # Il form principale e il pulsante di calcolo esistono.
    await expect(page.locator("#deduction-form")).to_be_visible()
    await expect(page.get_by_role("button", name="Calcola deduzione")).to_be_visible()


async def test_core_sections_present(live_server, page):
    await page.goto(live_server)
    # Card chiave del form.
    for text in ["Dati generali", "Indirizzi", "Trasporto", "Pasti fuori domicilio"]:
        await expect(page.get_by_role("heading", name=text).first).to_be_visible()
