"""E2E US-1106: pasti fuori domicilio e alloggio settimanale."""
import pytest
from playwright.async_api import expect

from .helpers import calcola, fill_minimal_addresses, results_text

pytestmark = pytest.mark.e2e


async def test_meal_section_toggle(live_server, page):
    """Deselezionando 'Includi deduzione pasti' la sezione si nasconde; riselezionando riappare."""
    await page.goto(live_server)
    group = page.locator("#meal-situation-group")
    await expect(group).to_be_visible()  # default: pasti inclusi
    await page.uncheck("#include_meals")
    await expect(group).to_be_hidden()
    await page.check("#include_meals")
    await expect(group).to_be_visible()


async def test_meal_situations_amounts(live_server, page):
    """Senza mensa (CHF 15/g -> 3'200) e con mensa (CHF 7.50/g -> 1'600) danno importi coerenti."""
    await page.goto(live_server)
    await fill_minimal_addresses(page)
    # Default: senza mensa.
    await calcola(page)
    text = await results_text(page)
    assert "Pasti fuori domicilio" in text
    assert "200.00" in text  # 3'200 senza mensa

    # Con mensa aziendale -> 1'600.
    await page.select_option("#meal_situation", "with_cafeteria")
    await calcola(page)
    text2 = await results_text(page)
    assert "600.00" in text2  # 1'600 con mensa


async def test_accommodation_card_visibility(live_server, page):
    """L'alloggio settimanale appare solo per 'Residente settimanale'."""
    await page.goto(live_server)
    await expect(page.locator("#accommodation-card")).to_be_hidden()
    await page.select_option("#residency_type", "weekly_resident")
    await expect(page.locator("#accommodation-card")).to_be_visible()
    await page.select_option("#residency_type", "resident_TI")
    await expect(page.locator("#accommodation-card")).to_be_hidden()


async def test_accommodation_cap_applied(live_server, page):
    """Costo alloggio oltre il tetto: applicato il cap (800/mese senza cucina -> 9'600/anno)."""
    await page.goto(live_server)
    await page.select_option("#residency_type", "weekly_resident")
    await fill_minimal_addresses(page)
    await page.uncheck("#include_meals")  # isola il contributo alloggio nel totale
    # Senza cucina (max 800/mese): inserisco 1'500 -> deve essere capato a 800.
    await page.check("input[name=accommodation_type][value=without_kitchen]")
    await page.fill("#accommodation_monthly_chf", "1500")

    await calcola(page)
    # Totale IC = trasporto ARCOBALENO 1'074 + alloggio capato 9'600 = 10'674.
    # Se NON fosse capato (1'500x12=18'000) il totale sarebbe 19'074: "674.00" sarebbe assente.
    await expect(page.locator("#total-can")).to_contain_text("674.00")
