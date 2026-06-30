"""E2E US-1109: mappa percorso (Leaflet markers + OSRM tollerante)."""
import pytest
from playwright.async_api import expect

from .helpers import calcola, fill_minimal_addresses, select_transport

pytestmark = pytest.mark.e2e


async def test_map_appears_with_markers(live_server, page):
    """Dopo il calcolo la mappa è visibile con i marker casa e lavoro (mezzi pubblici: niente OSRM)."""
    await page.goto(live_server)
    await fill_minimal_addresses(page)
    await calcola(page)

    map_section = page.locator("#map-section")
    await expect(map_section).to_be_visible()
    # Leaflet crea un marker per casa e uno per lavoro.
    await expect(page.locator("#route-map .leaflet-marker-icon")).to_have_count(2)


async def test_map_robust_to_osrm(live_server, page):
    """Auto privata: la mappa e i marker restano anche se OSRM (esterno) non risponde."""
    # Intercetta la chiamata OSRM esterna: il test non dipende dal tracciato reale.
    await page.route("**/router.project-osrm.org/**", lambda route: route.abort())
    await page.goto(live_server)
    await select_transport(page, "private_car")
    await fill_minimal_addresses(page)
    await page.fill("#override_distance_km", "28")
    await calcola(page)

    await expect(page.locator("#map-section")).to_be_visible()
    await expect(page.locator("#route-map .leaflet-marker-icon")).to_have_count(2)


async def test_reset_hides_map(live_server, page):
    """Premendo 'Azzera' la mappa viene rimossa e #map-section torna nascosta."""
    await page.goto(live_server)
    await fill_minimal_addresses(page)
    await calcola(page)
    await expect(page.locator("#map-section")).to_be_visible()

    await page.get_by_role("button", name="Azzera").click()
    await expect(page.locator("#map-section")).to_be_hidden()
    await expect(page.locator("#results")).to_be_hidden()
