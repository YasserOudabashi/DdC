"""E2E US-1110: generazione PDF e modalità accertamento."""
import pytest
from playwright.async_api import expect

from .helpers import calcola, fill_minimal_addresses

pytestmark = pytest.mark.e2e


async def test_download_pdf(live_server, page):
    """Dopo un calcolo, 'Scarica PDF' è visibile e il click genera un file .pdf."""
    await page.goto(live_server)
    await fill_minimal_addresses(page)
    await calcola(page)

    btn = page.locator("#btn-download-pdf")
    await expect(btn).to_be_visible()
    async with page.expect_download() as dl_info:
        await btn.click()
    download = await dl_info.value
    assert download.suggested_filename.endswith(".pdf")
    assert download.suggested_filename.startswith("deduzioni_")


async def test_assessment_mode_opens(live_server, page):
    """'Modalità accertamento' mostra banner, tabella editabile e sezione motivazione."""
    await page.goto(live_server)
    await fill_minimal_addresses(page)
    await calcola(page)

    await page.click("#btn-assessment-mode")
    await expect(page.locator("#assessment-banner")).to_be_visible()
    await expect(page.locator("#assessment-reason-section")).to_be_visible()
    # La tabella diventa editabile (input accertamento).
    await expect(page.locator("#results .assessment-input").first).to_be_visible()


async def test_assessment_requires_reason(live_server, page):
    """Scaricare il PDF accertato senza motivazione mostra l'errore e non avvia il download."""
    await page.goto(live_server)
    await fill_minimal_addresses(page)
    await calcola(page)
    await page.click("#btn-assessment-mode")

    # Nessuna motivazione inserita: il click mostra l'errore.
    await page.click("#btn-download-assessment")
    await expect(page.locator("#assessment-reason-error")).to_be_visible()
    await expect(page.locator("#assessment-reason-error")).to_contain_text("motivazione")


async def test_assessment_download_with_reason(live_server, page):
    """Con motivazione e un valore modificato, 'Scarica PDF accertato' avvia il download."""
    await page.goto(live_server)
    await fill_minimal_addresses(page)
    await calcola(page)
    await page.click("#btn-assessment-mode")

    await page.fill("#assessment-reason", "Rettifica del costo abbonamento secondo giustificativi.")
    first_input = page.locator("#results .assessment-input").first
    await first_input.fill("999.00")

    async with page.expect_download() as dl_info:
        await page.click("#btn-download-assessment")
    download = await dl_info.value
    assert download.suggested_filename.endswith(".pdf")
    assert download.suggested_filename.startswith("accertato_")
