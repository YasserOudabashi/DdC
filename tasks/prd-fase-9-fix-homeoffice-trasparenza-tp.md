# PRD: Fase 9 — Fix Home Office, Trasparenza Calcolo, Controllo Mezzi Pubblici

## Introduction

Questa fase risolve tre bug critici e aggiunge una feature informativa sul confronto mezzi pubblici/auto privata.

**Bug 1 (CRITICO):** Il frontend invia `days_per_week` e `home_office_days_per_week` al livello root del payload JSON, ma l'API Pydantic li aspetta annidati sotto `work_schedule`. Pydantic ignora i campi extra e usa i default (5 gg/sett., 0 HO), quindi i giorni effettivi sono sempre 220 indipendentemente dai giorni home office selezionati dall'utente.

**Bug 2:** La stringa `basis` per trasporto auto/moto mostra solo il numero finale di giorni (es. "176 giorni") senza spiegare il calcolo. Con HO attivo, l'utente non riesce a verificare che i giorni HO siano stati sottratti.

**Bug 3:** I pasti fuori domicilio vengono visualizzati in tabella con basis "—", senza mostrare la formula tariffa × giorni.

**Feature 4:** Quando l'utente usa l'auto privata, controllare se il domicilio è a ≤ 200m da una fermata di trasporto pubblico e mostrare un warning informativo se sì.

## Goals

- Correggere il bug HO che causa calcoli errati (effective_days sempre 220)
- Rendere visibile la formula di calcolo giorni effettivi quando HO > 0
- Mostrare la formula tariffa × giorni per i pasti fuori domicilio
- Avvisare l'utente quando una fermata TP è vicina al domicilio (≤ 200m), con calcolo auto comunque mantenuto
- Tutti i test esistenti passano senza regressioni

## User Stories

### US-901: Fix work_schedule nesting nel frontend

**Description:** As a user, I want the home office days I select to actually affect the calculation so that I receive the correct deduction amount.

**Acceptance Criteria:**

- [ ] In `app/static/js/app.js`, funzione `getFormPayload()`: sostituire i campi flat `days_per_week` e `home_office_days_per_week` nel payload root con l'oggetto annidato corretto:
  ```javascript
  // PRIMA (da rimuovere dal root del payload):
  //   days_per_week: daysPerWeek,
  //   home_office_days_per_week: homeOfficeDays,
  // DOPO (aggiungere al payload):
  work_schedule: {
    days_per_week: daysPerWeek,
    home_office_days_per_week: homeOfficeDays,
  },
  ```
- [ ] Test manuale: con 5 gg/sett, 1 gg HO, 1 km auto → cantonal net deve essere `0.6 × 1.0 × 2 × 176 = 211.20 CHF` (non 264.00 CHF)
- [ ] `uv run pytest tests/ -v` — tutti i test passano senza regressioni
- [ ] Avviare il server localmente (`uv run uvicorn app.main:app --reload --port 8000`) e verificare nel browser che cambiando i giorni HO il calcolo cambia

### US-902: Basis string trasparente per giorni effettivi (auto, moto, misto)

**Description:** As a user, I want the calculation formula to show how working days were computed from home office days so that I can verify the deduction is correct.

**Acceptance Criteria:**

- [ ] In `app/core/cantonal_engine.py`, funzioni `_private_car`, `_motorcycle`, `_mixed`:
  - La funzione riceve già `effective_days: int` e i dati del work_schedule devono essere passati o calcolati localmente
  - Cambiare la firma di `calculate_transport` per ricevere anche `work_schedule: WorkSchedule` (o solo `standard_annual: int` + `home_office_days_per_week: float`)
  - Se `home_office_days_per_week > 0`, aggiungere il suffisso esplicativo alla basis string:
    - Formato: `CHF {rate}/km × {km:.1f}km × 2 × {effective_days} giorni ({standard_annual}/5 sett. × {office_days_per_week:.0f} gg/sett. in ufficio)`
  - Se `home_office_days_per_week == 0`, la basis rimane come oggi: `CHF {rate}/km × {km:.1f}km × 2 × {effective_days} giorni`
- [ ] Stessa modifica in `app/core/federal_engine.py` per `_private_car`, `_motorcycle`, `_mixed`
- [ ] Il chiamante `calculator.py` aggiorna le chiamate a `cantonal_engine.calculate_transport` e `federal_engine.calculate_transport` passando `work_schedule=req.work_schedule`
- [ ] Esempio atteso con 5 gg/sett, 1 HO: `CHF 0.6/km × 1.0km × 2 × 176 giorni (220/5 sett. × 4 gg/sett. in ufficio)`
- [ ] Esempio atteso con 0 HO: `CHF 0.6/km × 1.0km × 2 × 220 giorni` (nessun suffisso)
- [ ] `uv run pytest tests/ -v` — tutti i test passano

### US-903: Meals basis text nella risposta e nel frontend

**Description:** As a user, I want to see the daily rate × days formula for meals so that I can verify that home office days were excluded.

**Acceptance Criteria:**

- [ ] In `app/schemas/response.py`, aggiungere campo opzionale a `TaxLevelResult`:
  ```python
  meals_basis_text: Optional[str] = None
  ```
- [ ] In `app/core/meals_engine.py`, le funzioni `calculate_meals_cantonal` e `calculate_meals_federal` ritornano una tupla `(float, str)` dove il secondo elemento è la stringa basis, oppure si aggiunge una funzione separata `calculate_meals_basis_text(...)`. Il testo deve avere formato: `CHF {rate}/giorno × {effective_days} giorni` (eventualmente con nota se il tetto è stato applicato: `→ tetto CHF {max:.0f}/anno`).
  - Esempio: `CHF 15.00/giorno × 176 giorni` (senza tetto)
  - Esempio: `CHF 15.00/giorno × 220 giorni → tetto CHF 3'200/anno applicato`
- [ ] In `app/core/calculator.py`, `_build_cantonal` e `_build_federal`: popolare `meals_basis_text` nel `TaxLevelResult`
- [ ] In `app/static/js/app.js`, funzione `buildDeductionTable`: sostituire la basis `—` per i pasti con `level.meals_basis_text || '—'`
- [ ] `uv run pytest tests/ -v` — tutti i test passano
- [ ] Avviare il server e verificare nel browser che la colonna basis per i pasti mostra la formula

### US-904: Warning prossimità fermata TP (distanza ≤ 200m)

**Description:** As a user choosing private car, I want to be informed if there's a public transport stop within 200m of my home so that I can evaluate whether the car deduction is appropriate.

**Acceptance Criteria:**

- [ ] Creare `app/geo/tp_proximity.py` con funzione asincrona:
  ```python
  async def find_nearest_stop(lat: float, lon: float, timeout: float = 3.0) -> tuple[str, float] | None:
  ```
  - Chiama `https://transport.opendata.ch/v1/locations?x={lon}&y={lat}&type=station&limit=1` via `httpx.AsyncClient`
  - Se la risposta contiene almeno una stazione, calcola la distanza in metri usando la formula di Haversine tra (lat, lon) e le coordinate della stazione
  - Ritorna `(nome_stazione, distanza_m)` oppure `None` se la chiamata fallisce, va in timeout, o non ci sono stazioni
- [ ] In `app/api/v1/endpoints/deduction.py`, nell'endpoint POST `/v1/deduction/calculate`:
  - Dopo aver risolto le coordinate del domicilio (geocoding già esistente), se `req.transport_mode == TransportMode.PRIVATE_CAR` e le coordinate del domicilio sono disponibili (geocoding riuscito):
    - Chiamare `tp_proximity.find_nearest_stop(lat, lon)`
    - Se il risultato non è None e la distanza è ≤ 200m: aggiungere alle `warnings` nella response il testo:
      `f"Fermata TP '{nome}' a {distanza:.0f}m dal domicilio — valutare deduzione per mezzi pubblici (Art. 25 LT)"`
  - Se il geocoding del domicilio non è disponibile o la chiamata a TP fallisce: ignorare silenziosamente (nessun errore verso il client)
- [ ] Il warning è **solo informativo**: il `net_deduction_chf` per l'auto viene calcolato normalmente anche se la fermata è vicina
- [ ] La `street` del domicilio NON è resa obbligatoria — il check avviene solo se le coordinate sono disponibili
- [ ] Test: mockare `find_nearest_stop` per ritornare `("Lugano, Piazza Dante", 150.0)` → il campo `warnings` della response contiene la stringa con "150m"
- [ ] Test: mockare `find_nearest_stop` per ritornare `None` → nessun warning aggiunto
- [ ] Test: mockare `find_nearest_stop` per ritornare `("Stazione", 250.0)` → nessun warning (distanza > 200m)
- [ ] `uv run pytest tests/ -v` — tutti i test passano

### US-905: Test suite Fase 9

**Description:** As a developer, I want automated tests for all Fase 9 fixes so regressions are caught immediately.

**Acceptance Criteria:**

- [ ] Creare `tests/unit/test_fase9_homeoffice.py` con:
  - `test_work_schedule_nested_payload`: POST a `/v1/deduction/calculate` con payload che include `work_schedule: {days_per_week: 5, home_office_days_per_week: 1}` e `transport_mode=private_car`, `override_distance_km=1.0` → `cantonal_TI.transport_deduction.effective_working_days == 176`
  - `test_work_schedule_zero_ho`: stessa richiesta con `home_office_days_per_week: 0` → `effective_working_days == 220`
  - `test_basis_text_with_ho`: con HO=1 → `cantonal_TI.transport_deduction.lines[0].basis` contiene "220/5" e "4 gg/sett"
  - `test_basis_text_without_ho`: con HO=0 → basis NON contiene "sett. in ufficio"
  - `test_meals_basis_text`: con `include_meals=True`, `meal_situation=without_cafeteria`, HO=1 → `cantonal_TI.meals_basis_text` contiene "15.00" e "176 giorni"
- [ ] `uv run pytest tests/ -v` — tutti i test passano (inclusi i nuovi)

## Functional Requirements

- FR-1: Il payload API deve ricevere `work_schedule: {days_per_week, home_office_days_per_week}` (già corretto nel backend) — il frontend deve inviarlo in questo formato
- FR-2: Quando `home_office_days_per_week > 0`, la basis string del trasporto deve mostrare la formula di derivazione dei giorni effettivi
- FR-3: Il campo `meals_basis_text` nella response deve mostrare la formula CHF/giorno × giorni effettivi
- FR-4: Il frontend deve mostrare `meals_basis_text` nella colonna basis della tabella risultati
- FR-5: Per `transport_mode=private_car` con geocoding disponibile, eseguire la query alla API transport.opendata.ch per trovare la fermata più vicina
- FR-6: Se la fermata è a ≤ 200m, aggiungere un warning informativo nella response (il calcolo auto rimane invariato)
- FR-7: Errori di rete verso transport.opendata.ch non devono propagarsi come errori al client

## Non-Goals

- Non rendere obbligatoria la `street` del domicilio
- Non bloccare la deduzione auto anche se la fermata è vicina (solo warning informativo)
- Non calcolare automaticamente il costo del trasporto pubblico alternativo
- Non mostrare mappe o visualizzazioni geografiche
- Non implementare la comparazione IC vs IFD per i mezzi pubblici

## Technical Considerations

- `httpx` è già una dipendenza del progetto (usato per locations endpoint)
- Il geocoding del domicilio avviene già nell'endpoint `deduction.py` — le coordinate sono disponibili localmente dopo la risoluzione
- La formula di Haversine per la distanza può essere implementata in poche righe senza dipendenze esterne
- La chiamata a transport.opendata.ch deve avere timeout breve (3s) e fallire silenziosamente
- Il campo `meals_basis_text` è opzionale per retrocompatibilità API

## Success Metrics

- Con 5 gg/sett e 1 HO, il calcolo mostra `effective_working_days = 176` (non 220)
- La basis string mostra la formula completa quando HO > 0
- La colonna basis per i pasti mostra la formula tariffa × giorni
- Il warning fermata TP appare quando la fermata è a ≤ 200m

## Open Questions

- (nessuna — tutti i requisiti sono sufficientemente definiti)
