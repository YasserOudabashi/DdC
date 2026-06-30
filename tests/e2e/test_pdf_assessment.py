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
    """Scaricare il PDF accertato senza commento generale mostra l'errore e non avvia il download."""
    await page.goto(live_server)
    await fill_minimal_addresses(page)
    await calcola(page)
    await page.click("#btn-assessment-mode")

    # Nessun commento generale inserito (e nessuna modifica): il click mostra l'errore.
    await page.click("#btn-download-assessment")
    await expect(page.locator("#assessment-reason-error")).to_be_visible()
    await expect(page.locator("#assessment-reason-error")).to_contain_text("commento generale")


async def test_assessment_per_row_reason_appears(live_server, page):
    """Modificando un importo compare il campo motivo per quella riga."""
    await page.goto(live_server)
    await fill_minimal_addresses(page)
    await calcola(page)
    await page.click("#btn-assessment-mode")

    reason_input = page.locator("#results .assessment-reason-input").first
    await expect(reason_input).to_be_hidden()
    await page.locator("#results .assessment-input").first.fill("999.00")
    await expect(reason_input).to_be_visible()


async def test_assessment_per_row_reason_required(live_server, page):
    """Modifica senza motivo per riga: il download è bloccato con errore."""
    await page.goto(live_server)
    await fill_minimal_addresses(page)
    await calcola(page)
    await page.click("#btn-assessment-mode")

    await page.fill("#assessment-reason", "Commento generale di prova.")
    await page.locator("#results .assessment-input").first.fill("999.00")
    # Motivo per riga NON compilato → blocco
    await page.click("#btn-download-assessment")
    await expect(page.locator("#assessment-reason-error")).to_be_visible()
    await expect(page.locator("#assessment-reason-error")).to_contain_text("voce modificata")


async def test_assessment_download_with_reason(live_server, page):
    """Con commento generale, valore modificato e motivo per riga, il download parte."""
    await page.goto(live_server)
    await fill_minimal_addresses(page)
    await calcola(page)
    await page.click("#btn-assessment-mode")

    await page.fill("#assessment-reason", "Rettifica del costo abbonamento secondo giustificativi.")
    await page.locator("#results .assessment-input").first.fill("999.00")
    await page.locator("#results .assessment-reason-input").first.fill("Importo rettificato su giustificativo.")

    async with page.expect_download() as dl_info:
        await page.click("#btn-download-assessment")
    download = await dl_info.value
    assert download.suggested_filename.endswith(".pdf")
    assert download.suggested_filename.startswith("accertato_")

    # Verifica che l'importo accertato e il motivo siano effettivamente nel PDF
    # (jsPDF non comprime gli stream di testo → leggibili nel byte-stream).
    import pathlib
    path = await download.path()
    content = pathlib.Path(path).read_bytes().decode("latin-1")
    assert "999.00" in content, "L'importo accertato 999.00 non compare nel PDF"
    assert "Importo rettificato" in content, "Il motivo per riga non compare nel PDF"
