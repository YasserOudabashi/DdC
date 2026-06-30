"""E2E US-1107: Lohnausweis (D/F/auto aziendale) + altre spese + attività accessoria."""
import pytest
from playwright.async_api import expect

from .helpers import calcola, fill_minimal_addresses, results_text, select_transport

pytestmark = pytest.mark.e2e


async def test_campo_d_zeroes_transport(live_server, page):
    """Campo D (employer_pays_transport): la deduzione trasporto netta è azzerata."""
    await page.goto(live_server)
    await fill_minimal_addresses(page)
    await page.check("#employer_pays_transport")
    results = await calcola(page)
    await expect(results).to_contain_text("Trasporto a carico del datore di lavoro")


async def test_campo_f_reduced_meals(live_server, page):
    """Campo F (employer_has_cafeteria): i pasti usano la tariffa ridotta (CHF 7.50 -> 1'600)."""
    await page.goto(live_server)
    await fill_minimal_addresses(page)
    # Pasti inclusi, situazione 'senza mensa', ma Campo F forza la tariffa mensa.
    await page.check("#employer_has_cafeteria")
    results = await calcola(page)
    text = await results_text(page)
    assert "Pasti fuori domicilio" in text
    assert "600.00" in text  # 1'600 (7.50/g) invece di 3'200 (15/g)


async def test_company_car_forfait(live_server, page):
    """Auto aziendale (cifra 13.2.2): compare il campo e il trasporto usa il forfait Art. 5a."""
    await page.goto(live_server)
    await select_transport(page, "private_car")
    await expect(page.locator("#company-car-group")).to_be_visible()
    await fill_minimal_addresses(page)
    await page.fill("#override_distance_km", "28")
    await page.fill("#company_car_monthly_chf", "300")
    results = await calcola(page)
    await expect(results).to_contain_text("Auto aziendale")


async def test_company_car_group_hidden_for_pt(live_server, page):
    """#company-car-group è visibile solo con 'Auto privata'."""
    await page.goto(live_server)
    await expect(page.locator("#company-car-group")).to_be_hidden()  # default: mezzi pubblici


async def test_other_expenses_effettive(live_server, page):
    """Altre spese: con 'effettive' compare l'importo e si applica il maggiore tra forfait ed effettive."""
    await page.goto(live_server)
    await fill_minimal_addresses(page)
    await page.uncheck("#include_meals")
    await page.check("#include_other_expenses")
    await expect(page.locator("#other-expenses-details")).to_be_visible()
    await page.check("input[name=other_expenses_method][value=effettive]")
    await expect(page.locator("#actual-other-expenses-group")).to_be_visible()
    await page.fill("#actual_other_expenses_chf", "4500")  # > forfait 3'000

    results = await calcola(page)
    text = await results_text(page)
    assert "Altre spese professionali" in text
    assert "500.00" in text  # 4'500 effettive applicate (forfait 3'000 darebbe 000.00)


async def test_secondary_activity_included(live_server, page):
    """Attività accessoria: compare la sezione e la deduzione aumenta il totale IFD."""
    await page.goto(live_server)
    await fill_minimal_addresses(page)
    await page.uncheck("#include_meals")
    # Il salario (necessario al calcolo IFD accessoria) sta nella sezione altre spese.
    await page.check("#include_other_expenses")
    await page.fill("#annual_net_salary_chf", "75000")

    # Totale IFD senza attività accessoria.
    await calcola(page)
    total_before = await page.locator("#total-fed").inner_text()

    # Attiva attività accessoria.
    await page.check("#include_secondary_activity")
    await expect(page.locator("#secondary-activity-details")).to_be_visible()
    await calcola(page)
    total_after = await page.locator("#total-fed").inner_text()

    assert total_before != total_after  # la deduzione accessoria è inclusa nel totale IFD
