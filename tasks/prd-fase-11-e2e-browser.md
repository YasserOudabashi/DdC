# PRD: Fase 11 — Verifica End-to-End nel Browser (Playwright)

## Introduction

La Fase 11 non aggiunge funzionalità: **verifica nel browser** che tutto il sito
funzioni correttamente dal punto di vista dell'utente. Copre ogni percorso del form
(tutti i mezzi di trasporto, pasti, alloggio settimanale, Lohnausweis, coniuge,
mappa, PDF, modalità accertamento, validazioni e usabilità) con test end-to-end
Playwright che girano contro l'app reale.

**Stack di test:** `playwright` (API **async**, integrata con `asyncio_mode=auto`) +
uvicorn avviato **in-process** in un thread. Il geocoder è stubbato in modo deterministico
(`tests/e2e/conftest.py`, fixture function-scoped che ripristina dopo ogni test) così i test
non dipendono da swisstopo / nominatim / OSRM e sono riproducibili in CI/Docker.

> ⚠️ Non usare `pytest-playwright` (API sync/greenlet): confligge con `asyncio_mode=auto`
> e lascia un event loop attivo che fa fallire i test backend async.

## Goals

- Garantire che ogni flusso utente produca risultati IC+IFD corretti e coerenti.
- Verificare la UI condizionale (sezioni che appaiono/scompaiono) e le validazioni.
- Coprire mappa, generazione PDF e modalità accertamento dal punto di vista dell'utente.
- Nessuna regressione: `uv run pytest tests/ -v` resta verde (backend + E2E).

## Prerequisiti

```bash
uv sync --group dev
uv run playwright install chromium
uv run pytest tests/ -v
```

## User Stories

| ID | Priorità | Titolo |
|----|----------|--------|
| US-1101 | 1 | Infrastruttura E2E Playwright (server in-process + stub geocoder) |
| US-1102 | 2 | E2E mezzi pubblici ARCOBALENO (happy path IC+IFD) |
| US-1103 | 3 | E2E auto privata (blocco <30km, override distanza, warning cap IFD) |
| US-1104 | 4 | E2E moto targa bianca e bicicletta |
| US-1105 | 5 | E2E trasporto misto (auto + treno) |
| US-1106 | 6 | E2E pasti e alloggio settimanale |
| US-1107 | 7 | E2E Lohnausweis + altre spese + attività accessoria |
| US-1108 | 8 | E2E coniuge / partner registrato |
| US-1109 | 9 | E2E mappa percorso (Leaflet + OSRM tollerante) |
| US-1110 | 10 | E2E PDF e modalità accertamento |
| US-1111 | 11 | E2E validazioni form e usabilità |

I criteri di accettazione dettagliati per ogni storia sono in `prd.json`
(campo `acceptanceCriteria`). Ogni storia si chiude con
`uv run pytest tests/ -v` verde, senza regressioni.

## Note tecniche (vedi anche progress.txt)

- **Indirizzi/città**: TomSelect con `create:true` → digitare il nome + Invio,
  impostare l'NPA *dopo* la città. Usare `tests/e2e/helpers.py`.
- **Distanze deterministiche**: lo stub geo usa coordinate fisse; i km sono calcolati
  dal codice reale (haversine × fattore). Coppie utili:
  Bellinzona(6500)→Lugano(6900) ≈ 30 km; Bellinzona→Giubiasco(6512) < 5 km (blocco auto).
- **OSRM** (router.project-osrm.org) è esterno: stubbare con `page.route` o asserire
  solo presenza mappa + marker.
- **PDF** (jsPDF, lato browser): usare `page.expect_download`.
- I test E2E sono **async** (`playwright.async_api`), coerenti con `asyncio_mode=auto`.
- Lo stub geo è **function-scoped** e ripristina lo stato del modulo dopo ogni test:
  un session-scope farebbe fallire i test backend con 422.

## Come eseguire la fase con Ralph

```bash
cd "D:\006-Documenti\Lavori\DdC\002_Applicativo"
# con Docker Desktop avviato:
bash /c/Users/oudab/.claude/skills/ralph.sh 11
```

Il `prd.json` contiene SOLO le storie di Fase 11, quindi non serve `--fase`.
