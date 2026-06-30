"""
Infrastruttura E2E browser (Fase 11).

Avvia l'app FastAPI con uvicorn **in-process** (thread) e stubba il geocoder
in modo deterministico, così i test Playwright non dipendono da servizi esterni
(swisstopo / nominatim / OSRM proximity) e sono riproducibili in CI / Docker.

Fixtures esposte:
  - live_server -> base URL "http://127.0.0.1:<porta>" del sito reale
  - geo_table   -> dict coordinate usate dallo stub (per asserzioni nei test)
  - page        -> fornita da pytest-playwright

Tabella coordinate (lat, lon) — valori realistici ma fissi:
  - i km vengono calcolati dal codice reale (road_distance_km, haversine*factor),
    quindi le distanze sono deterministiche e coerenti con la logica fiscale.
"""
from __future__ import annotations

import socket
import threading
import time

import pytest
import pytest_asyncio
import uvicorn
from playwright.async_api import async_playwright

# --- Coordinate deterministiche (lat, lon) -------------------------------------
# Le chiavi sono sottostringhe cercate nell'indirizzo completo (NPA o città).
# Distanze reali approssimate dalla coppia di coordinate:
#   6500 Bellinzona  <-> 6900 Lugano   ~ 25-30 km stradali
#   6500 Bellinzona  <-> 6512 (vicino) ~ < 5 km   (per test blocco auto <30km)
#   6900 Lugano      <-> 22100 Como IT ~ frontaliere
GEO_COORDS = {
    "6500": (46.1944, 9.0244),    # Bellinzona
    "Bellinzona": (46.1944, 9.0244),
    "6900": (46.0037, 8.9511),    # Lugano
    "Lugano": (46.0037, 8.9511),
    "6600": (46.1712, 8.7943),    # Locarno
    "Locarno": (46.1712, 8.7943),
    "6830": (45.8331, 9.0306),    # Chiasso
    "Chiasso": (45.8331, 9.0306),
    "6512": (46.2089, 9.0156),    # Giubiasco (vicino Bellinzona, < 5 km)
    "Giubiasco": (46.2089, 9.0156),
    "22100": (45.8081, 9.0852),   # Como (IT) — frontaliere
    "Como": (45.8081, 9.0852),
}
_DEFAULT_COORDS = (46.0101, 8.9600)


@pytest.fixture(scope="session")
def geo_table() -> dict:
    return dict(GEO_COORDS)


def _lookup(address: str):
    for key, coords in GEO_COORDS.items():
        if key in address:
            return coords
    return _DEFAULT_COORDS


@pytest.fixture(autouse=True)
def _stub_geo():
    """Sostituisce geocoder + TP-proximity con versioni deterministiche.

    Function-scoped: ripristina lo stato del modulo dopo OGNI test e2e, così non
    inquina i test backend (che girano nella stessa sessione pytest).
    """
    from app.geo import resolver, tp_proximity
    from app.geo.providers.base import GeoResolved

    async def fake_resolve_detailed(address: str):
        lat, lon = _lookup(address)
        # postcode/city None → la validazione NPA viene saltata (nessun warning spurio)
        return GeoResolved(lat=lat, lon=lon)

    async def fake_nearest_stop(lat: float, lon: float):
        # Nessuna fermata "vicina" di default: non blocca l'auto via TP.
        return None

    orig_sw = resolver._swisstopo.resolve_detailed
    orig_no = resolver._nominatim.resolve_detailed
    orig_stop = tp_proximity.find_nearest_stop

    resolver._swisstopo.resolve_detailed = fake_resolve_detailed
    resolver._nominatim.resolve_detailed = fake_resolve_detailed
    tp_proximity.find_nearest_stop = fake_nearest_stop
    try:
        yield
    finally:
        resolver._swisstopo.resolve_detailed = orig_sw
        resolver._nominatim.resolve_detailed = orig_no
        tp_proximity.find_nearest_stop = orig_stop


@pytest.fixture(scope="session")
def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def live_server(_free_port) -> str:
    """Avvia uvicorn in un thread e ritorna la base URL del sito.

    Lo stub geocoder è applicato separatamente da _stub_geo (autouse, per-test):
    le richieste leggono gli attributi patchati al momento della richiesta.
    """
    from app.main import app

    config = uvicorn.Config(
        app, host="127.0.0.1", port=_free_port, log_level="warning", lifespan="on"
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base = f"http://127.0.0.1:{_free_port}"
    # attesa readiness (max ~10s)
    for _ in range(100):
        try:
            with socket.create_connection(("127.0.0.1", _free_port), timeout=0.2):
                break
        except OSError:
            time.sleep(0.1)
    else:
        raise RuntimeError("live_server non è partito in tempo")

    yield base

    server.should_exit = True
    thread.join(timeout=5)


@pytest_asyncio.fixture
async def page():
    """Pagina Chromium (API async) — function-scoped, coerente con asyncio_mode=auto.

    Usa l'API async di Playwright per integrarsi con pytest-asyncio senza il
    greenlet/loop dell'API sync (che confliggerebbe con i test backend async).
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        pg = await context.new_page()
        try:
            yield pg
        finally:
            await context.close()
            await browser.close()
