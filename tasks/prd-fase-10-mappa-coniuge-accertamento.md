# PRD: Fase 10 — Mappa Tragitto, Coniuge/Partner, Modalità Accertamento

## Introduction

Fase 10 aggiunge tre funzionalità indipendenti al web service DdC:

1. **Mappa tragitto** — visualizza il percorso casa-lavoro su mappa OpenStreetMap dopo il calcolo, adattandosi al mezzo scelto (auto, bici, moto, TP).
2. **Coniuge/partner registrato** — aggiunge una sezione opzionale nel form e nel backend per calcolare le deduzioni del coniuge/partner attivo professionalmente (Modulo 4, pagina 2), con risultati IC+IFD separati.
3. **Modalità accertamento** — permette ai tassatori di modificare inline i valori calcolati, inserire una motivazione, e scaricare un PDF "accertato". Il PDF senza modifiche è scaricabile sempre.

**Stack attuale:** FastAPI + Pydantic backend, HTML/JS vanilla frontend, Leaflet.js già incluso via CDN locale, Tom Select per autocomplete.

---

## Goals

- Mostrare il percorso casa-lavoro su mappa senza ricadere su provider a pagamento.
- Supportare il calcolo per coniuge/partner senza rompere la retrocompatibilità (campo `spouse` opzionale).
- Consentire ai tassatori di produrre un PDF "accertato" modificando i valori nella tabella, senza login, senza DB.
- Permettere a chiunque di scaricare il PDF del risultato calcolato in un click.

---

## User Stories

### US-1001: Coordinate geocodificate nella response API

**Description:** As a frontend developer, I want the geocoded coordinates of home and work addresses in the API response so that I can display the route on a map without a second API call.

**Acceptance Criteria:**

- [ ] In `app/schemas/response.py`, aggiungere la classe `Coordinates(BaseModel)` con campi `lat: float` e `lon: float`.
- [ ] In `DeductionResponse`, aggiungere i campi opzionali: `home_coordinates: Optional[Coordinates] = None` e `work_coordinates: Optional[Coordinates] = None`.
- [ ] In `app/api/v1/endpoints/deduction.py` (o in `calculator.py`), dopo il geocoding, popolare `home_coordinates` e `work_coordinates` con le coordinate restituite dal geocoder (lat/lon).
- [ ] Se il geocoding non è disponibile o fallisce, i campi rimangono `None` senza errori.
- [ ] Test: POST con indirizzi validi CH → response include `home_coordinates.lat`, `home_coordinates.lon`, `work_coordinates.lat`, `work_coordinates.lon` (valori float non nulli).
- [ ] `uv run pytest tests/ -v` — tutti i test passano senza regressioni.

---

### US-1002: Mappa Leaflet nella sezione risultati (markers)

**Description:** As a user, I want to see a map showing my home and work locations after calculating so that I can visually confirm the route.

**Acceptance Criteria:**

- [ ] In `app/static/index.html`, aggiungere dopo la sezione risultati (dopo `#results-section`) un div `id="map-section"` con `class="card hidden"` contenente:
  - Titolo `<h2 class="card-title">Percorso casa-lavoro</h2>`
  - Un div `id="route-map"` con `style="height:320px; border-radius:8px; overflow:hidden;"`
- [ ] Aggiungere Leaflet CSS e JS via CDN (unpkg, versione 1.9.x) prima di `</head>`:
  ```html
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  ```
- [ ] In `app/static/js/app.js`, dopo aver ricevuto una response con successo: se `data.home_coordinates` e `data.work_coordinates` non sono null:
  - Mostrare `#map-section` (rimuovere `hidden`).
  - Inizializzare (o aggiornare) la mappa Leaflet su `#route-map` con tile layer OpenStreetMap: `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`, attribution `© OpenStreetMap contributors`.
  - Aggiungere marker verde "Casa" su `home_coordinates` e marker rosso "Lavoro" su `work_coordinates`.
  - Fare `fitBounds` ai due punti con padding `[40, 40]`.
- [ ] Se le coordinate sono null, `#map-section` rimane nascosta.
- [ ] Variabile `let leafletMap = null` globale; se la mappa esiste già, chiamare `leafletMap.remove()` prima di reinizializzarla (evita errori sul secondo calcolo).
- [ ] In `btnReset` handler: se `leafletMap` non è null → `leafletMap.remove(); leafletMap = null;`; nascondere `#map-section`.
- [ ] `uv run pytest tests/ -v` — tutti i test passano senza regressioni backend.
- [ ] Verificare in browser: dopo calcolo con indirizzi TI → mappa visibile con 2 marker.

---

### US-1003: Tracciato del percorso via OSRM (auto e bici)

**Description:** As a user, I want to see the actual route drawn on the map so that I can verify that the path matches my daily commute.

**Acceptance Criteria:**

- [ ] In `app/static/js/app.js`, in aggiunta ai marker, se `transport_mode` è `private_car`, `motorcycle` o `mixed`: chiamare l'API pubblica OSRM con profilo `driving`:
  `https://router.project-osrm.org/route/v1/driving/{home_lon},{home_lat};{work_lon},{work_lat}?overview=full&geometries=geojson`
- [ ] Se `transport_mode` è `bicycle`: usare profilo `cycling` (stesso URL, profilo diverso).
- [ ] Parsare la risposta OSRM: `data.routes[0].geometry` (GeoJSON LineString) → aggiungere polyline blu (`color: '#003366', weight: 4, opacity: 0.75`) sulla mappa.
- [ ] Se `transport_mode` è `public_transport`: NON chiamare OSRM; mostrare solo i 2 marker e una nota testuale sotto la mappa: `<p class="field-hint" id="map-note">Percorso mezzi pubblici non disponibile — visualizzati solo i punti di partenza e arrivo.</p>`
- [ ] Se la chiamata OSRM fallisce o va in timeout (3 secondi): mostrare solo i 2 marker, senza errori verso l'utente.
- [ ] Variabile `let osrmPolyline = null`; se esiste già, rimuoverla prima di aggiungerne una nuova.
- [ ] `uv run pytest tests/ -v` — tutti i test passano senza regressioni backend.
- [ ] Verificare in browser: auto → percorso stradale; bici → percorso ciclabile; TP → solo markers + nota.

---

### US-1004: Schema backend coniuge/partner (`SpouseRequest` + `SpouseResponse`)

**Description:** As a developer, I want a `spouse` field in the request and response schemas so that the API can calculate deductions for the spouse/registered partner independently.

**Acceptance Criteria:**

- [ ] In `app/schemas/request.py`, aggiungere la classe `SpouseRequest(BaseModel)` con gli stessi campi opzionali di `DeductionRequest` relativi alle spese personali (escludere `fiscal_year` e `residency_type` che si ereditano dal contribuente principale):
  - `home_address: Optional[Address] = None` — se None, usa l'indirizzo del contribuente
  - `work_address: Address` — obbligatorio
  - `transport_mode: TransportMode`
  - `work_schedule: WorkSchedule = Field(default_factory=WorkSchedule)`
  - `meal_situation: MealSituation = MealSituation.HOME`
  - `override_distance_km: Optional[float] = Field(default=None, ge=0.1, le=500.0)`
  - `annual_public_transport_cost_chf: Optional[float] = Field(default=None, ge=0.0, le=20_000.0)`
  - `arcobaleno_zones: Optional[int] = Field(default=None, ge=1, le=8)`
  - `arcobaleno_class: str = Field(default='2', pattern=r'^[12]$')`
  - `annual_net_salary_chf: Optional[float] = Field(default=None, ge=0.0, le=1_000_000.0)`
  - `employer_pays_transport: bool = Field(default=False)`
  - `employer_has_cafeteria: bool = Field(default=False)`
  - `company_car_monthly_chf: Optional[float] = Field(default=None, ge=0.0, le=2_000.0)`
  - `include_meals: bool = Field(default=False)`
  - `include_other_expenses: bool = Field(default=False)`
  - `actual_other_expenses_chf: Optional[float] = Field(default=None, ge=0.0, le=50_000.0)`
  - `include_secondary_activity: bool = Field(default=False)`
  - `actual_secondary_activity_chf: Optional[float] = Field(default=None, ge=0.0, le=500_000.0)`
  - Stessi `model_validator` di `DeductionRequest` per arcobaleno (zones + class incompatibili, arcobaleno richiede public_transport).
- [ ] In `DeductionRequest`, aggiungere campo `spouse: Optional[SpouseRequest] = None`.
- [ ] In `app/schemas/response.py`, aggiungere in `DeductionResponse`: `spouse: Optional[SpouseResult] = None` dove `SpouseResult` è una nuova classe con:
  - `cantonal_TI: TaxLevelResult`
  - `federal_IFD: TaxLevelResult`
  - `distance_km: Optional[float] = None`
  - `geocoding_used: bool = False`
  - `home_coordinates: Optional[Coordinates] = None`
  - `work_coordinates: Optional[Coordinates] = None`
- [ ] Se `req.spouse` è None, `response.spouse` è None (retrocompatibile).
- [ ] Typecheck/lint passa.
- [ ] `uv run pytest tests/ -v` — tutti i test passano senza regressioni.

---

### US-1005: Calcolo backend coniuge nel calculator

**Description:** As a developer, I want the calculator to compute deductions for the spouse using the same engines as the main taxpayer so that results are consistent.

**Acceptance Criteria:**

- [ ] In `app/core/calculator.py`, aggiungere funzione `calculate_spouse(req: DeductionRequest, rules: FiscalYearRules) -> SpouseResult` (o integrare in `calculate()`).
- [ ] Se `req.spouse` è None, non fare nulla e lasciare `response.spouse = None`.
- [ ] Se `req.spouse` è presente:
  - L'indirizzo di domicilio del coniuge è `req.spouse.home_address if req.spouse.home_address else req.home_address`.
  - Il `fiscal_year` e il `residency_type` vengono ereditati da `req` (non si sovrascrivono per il coniuge).
  - Richiamare le stesse funzioni di calcolo cantonal e federal con i dati del coniuge.
  - Il geocoding viene eseguito per l'indirizzo del coniuge (può essere diverso dal contribuente).
- [ ] Test: POST con `spouse` presente → `response.spouse.cantonal_TI.total_deduction_chf > 0`.
- [ ] Test: POST senza `spouse` → `response.spouse` è `null` in JSON.
- [ ] Test: `spouse.home_address = null` → viene usato l'indirizzo del contribuente.
- [ ] `uv run pytest tests/ -v` — tutti i test passano.

---

### US-1006: Frontend — sezione form coniuge/partner

**Description:** As a user, I want to optionally add my spouse/partner's data so that I can calculate their deductions in the same session.

**Acceptance Criteria:**

- [ ] In `app/static/index.html`, aggiungere dopo il form del contribuente (prima del `<button type="submit">`) una card collassabile `id="spouse-card"` con:
  - Checkbox `id="include_spouse"` con label "Includi coniuge/partner registrato".
  - Div `id="spouse-fields"` con `class="hidden"` che contiene tutti gli stessi campi del contribuente (escluso anno fiscale e tipo residenza):
    - Sezione indirizzi: stessa struttura, IDs con prefisso `sp_` (es. `sp_work_city`, `sp_work_street`, ecc.).
    - Checkbox opzionale "Domicilio uguale al contribuente" (`id="sp_same_home"`) che, se spuntato, nasconde i campi domicilio del coniuge e usa i valori del contribuente.
    - Sezione trasporto: stesso select mezzo con IDs `sp_transport_mode`, `sp_arcobaleno_zones`, ecc.
    - Sezione orario: `sp_days_per_week`, `sp_home_office_days`.
    - Sezione pasti: `sp_meal_situation`, `sp_include_meals`.
    - Sezione altre spese: `sp_include_other_expenses`, `sp_annual_net_salary_chf`.
- [ ] In `app/static/js/app.js`:
  - Listener su `#include_spouse`: toggle visibilità `#spouse-fields`.
  - Listener su `#sp_same_home`: toggle visibilità sezione indirizzi domicilio coniuge.
  - In `getFormPayload()`: se `#include_spouse` è spuntato, costruire l'oggetto `spouse` con tutti i dati del coniuge e aggiungerlo al payload; altrimenti omettere il campo.
  - Sezione TP coniuge: stessa logica ARCOBALENO/manuale/SBB con IDs `sp_pt_cost_type`, `sp_arcobaleno_zones`, ecc.
- [ ] In `validateForm()`: se `#include_spouse` spuntato, validare anche i campi coniuge (lavoro obbligatorio, mezzo obbligatorio, ecc.).
- [ ] `uv run pytest tests/ -v` — tutti i test passano senza regressioni.
- [ ] Verificare in browser: checkbox → sezione compare; compilare → dati inclusi nel payload.

---

### US-1007: Frontend — risultati coniuge nella sezione output

**Description:** As a user, I want to see the spouse's deduction results displayed separately after the main taxpayer's results so that I can compare them easily.

**Acceptance Criteria:**

- [ ] In `app/static/js/app.js`, in `renderResults()`: se `data.spouse` non è null, aggiungere una seconda card risultati sotto quella del contribuente con titolo "Coniuge/Partner registrato".
- [ ] La struttura HTML della card coniuge è identica a quella del contribuente (stessa tabella IC/IFD) ma con i dati di `data.spouse`.
- [ ] Se `data.spouse` è null, nessuna seconda card viene mostrata.
- [ ] Mappa coniuge: se `data.spouse.home_coordinates` e `data.spouse.work_coordinates` sono presenti, aggiungere marker aggiuntivi con icona diversa (es. triangolo) sulla stessa mappa già mostrata per il contribuente. Non creare una seconda mappa.
- [ ] `uv run pytest tests/ -v` — tutti i test passano senza regressioni.
- [ ] Verificare in browser: con coniuge compilato → due card risultati; senza coniuge → una sola card.

---

### US-1008: Pulsante "Scarica PDF" sempre disponibile (risultato senza modifiche)

**Description:** As a user, I want to download the calculated result as a PDF immediately after calculation so that I can save or print it.

**Acceptance Criteria:**

- [ ] Aggiungere jsPDF via CDN (unpkg, versione 2.x) prima di `</head>` in `index.html`:
  ```html
  <script src="https://unpkg.com/jspdf@2.5.1/dist/jspdf.umd.min.js"></script>
  ```
- [ ] In `app/static/index.html`, nella sezione risultati aggiungere un pulsante `id="btn-download-pdf"` con label "Scarica PDF" (icona download opzionale), visibile solo quando i risultati sono presenti.
- [ ] In `app/static/js/app.js`, implementare `generatePdf(assessmentMode = false)`:
  - Crea PDF A4 verticale con jsPDF.
  - Intestazione: "Calcolo Deduzioni Trasferta — Canton Ticino", anno fiscale, data generazione.
  - Tabella IC: stessa struttura della tabella nel frontend (Voce / Importo CHF / Base di calcolo / Rif. legale).
  - Tabella IFD: idem.
  - Se `assessmentMode = false`: non mostra colonna "Accertato", non mostra campo motivazione.
  - Footer: "Documento generato automaticamente — non ha valore legale."
  - Scarica il file con nome `deduzioni_[anno]_[data].pdf`.
- [ ] Click su `#btn-download-pdf` → chiama `generatePdf(false)`.
- [ ] `uv run pytest tests/ -v` — tutti i test passano senza regressioni.
- [ ] Verificare in browser: click → download PDF con tabella IC e IFD corrette.

---

### US-1009: Attivazione modalità accertamento

**Description:** As a tax assessor, I want to activate an assessment mode so that I can review and correct the calculated deductions.

**Acceptance Criteria:**

- [ ] In `app/static/index.html`, nella sezione risultati aggiungere un pulsante `id="btn-assessment-mode"` con label "Modalità accertamento" (visibile solo quando i risultati sono presenti), con stile distinto (es. outline o secondario).
- [ ] In `app/static/js/app.js`, variabile booleana `let assessmentActive = false`.
- [ ] Click su `#btn-assessment-mode`:
  - Alternare `assessmentActive`.
  - Se `true`: cambiare label in "Esci da modalità accertamento"; mostrare un banner giallo `id="assessment-banner"` sopra la tabella con testo: "Modalità accertamento attiva — modificare i valori nella tabella e inserire la motivazione prima di scaricare il PDF accertato."
  - Se `false`: nascondere banner, ripristinare label originale, rimuovere eventuali input inline, rirenderizzare la tabella con i valori calcolati originali.
- [ ] Il pulsante `#btn-download-pdf` rimane sempre visibile e funzionante (scarica il risultato originale senza modifiche).
- [ ] `uv run pytest tests/ -v` — tutti i test passano senza regressioni.
- [ ] Verificare in browser: click attiva/disattiva modalità; banner compare/scompare.

---

### US-1010: Tabella editabile in modalità accertamento + campo motivazione

**Description:** As a tax assessor, I want to edit the deduction amounts directly in the table and provide a reason for the changes so that the PDF reflects the official assessment.

**Acceptance Criteria:**

- [ ] In `app/static/js/app.js`, in `renderResults()`: se `assessmentActive = true`, sostituire ogni cella `amount_chf` della tabella con un `<input type="number" class="assessment-input" step="0.01" value="[valore originale]" data-original="[valore originale]">`.
- [ ] Le celle "Base di calcolo" e "Rif. legale" rimangono testo non editabile.
- [ ] Il totale della tabella si aggiorna in tempo reale quando l'utente modifica un valore (listener `input` su tutti `.assessment-input`).
- [ ] Se un valore viene modificato rispetto all'originale, evidenziare la cella (es. bordo arancione o sfondo giallo chiaro).
- [ ] Aggiungere sotto le tabelle un div `id="assessment-reason-section"` (visibile solo in modalità accertamento) con:
  - Label: "Motivazione delle modifiche (obbligatoria per il PDF accertato)"
  - `<textarea id="assessment-reason" rows="4" maxlength="1000" placeholder="Indicare il motivo delle rettifiche apportate..."></textarea>`
- [ ] `uv run pytest tests/ -v` — tutti i test passano senza regressioni.
- [ ] Verificare in browser: modalità accertamento → valori editabili; modifica → totale si aggiorna; cella modificata evidenziata.

---

### US-1011: "Scarica accertato PDF" con valori originali, accertati e motivazione

**Description:** As a tax assessor, I want to download a PDF showing both the calculated values and my corrections, with the reason for changes, so that it serves as the official assessment document.

**Acceptance Criteria:**

- [ ] In `app/static/index.html`, aggiungere pulsante `id="btn-download-assessment"` con label "Scarica accertato PDF", visibile solo quando `assessmentActive = true`.
- [ ] Click su `#btn-download-assessment`:
  - Se `#assessment-reason` è vuoto → mostrare messaggio di errore inline: "Inserire la motivazione prima di scaricare il PDF accertato." Non generare il PDF.
  - Altrimenti: chiamare `generatePdf(true)`.
- [ ] In `generatePdf(true)`, rispetto alla versione senza modifiche:
  - Intestazione aggiuntiva: "DOCUMENTO DI ACCERTAMENTO" in grassetto.
  - Ogni tabella ha colonne: Voce / Calcolato CHF / **Accertato CHF** / Base di calcolo.
  - Le righe con valore modificato mostrano il valore originale barrato (o in grigio) nella colonna "Calcolato" e il valore accertato in grassetto nella colonna "Accertato".
  - Le righe non modificate mostrano lo stesso valore in entrambe le colonne.
  - Sezione "Motivazione delle modifiche": il testo inserito in `#assessment-reason`.
  - Footer: "Documento di accertamento generato il [data] — verificare con l'autorità fiscale competente."
  - Nome file: `accertato_[anno]_[data].pdf`.
- [ ] `uv run pytest tests/ -v` — tutti i test passano senza regressioni.
- [ ] Verificare in browser: senza motivazione → errore; con motivazione → download PDF con sezioni corrette.

---

### US-1012: Test suite Fase 10 (backend)

**Description:** As a developer, I want automated tests for all Fase 10 backend changes so regressions are caught immediately.

**Acceptance Criteria:**

- [ ] Creare `tests/unit/test_fase10_spouse.py` con i seguenti test:
  - `test_spouse_none_response`: POST senza campo `spouse` → `response.spouse` è `null`.
  - `test_spouse_same_home`: POST con `spouse.home_address = null` → usa home del contribuente (nessun errore).
  - `test_spouse_independent_calculation`: POST con `spouse.work_address` diverso → `response.spouse.cantonal_TI.total_deduction_chf` è calcolato indipendentemente.
  - `test_spouse_arcobaleno`: POST con `spouse.arcobaleno_zones = 3` → `response.spouse.cantonal_TI.transport_deduction.net_deduction_chf == 1074.0`.
  - `test_coordinates_in_response`: POST con indirizzi TI → `response.home_coordinates` non è null; `response.home_coordinates.lat` è un float; stessa verifica per `work_coordinates`.
  - `test_coordinates_none_if_geocoding_fails`: simulare fallimento geocoding → `response.home_coordinates` è null, nessuna eccezione.
- [ ] `uv run pytest tests/unit/test_fase10_spouse.py -v` — tutti i test passano.
- [ ] `uv run pytest tests/ -v` — tutti i test passano senza regressioni.

---

## Functional Requirements

- **FR-1:** Il backend aggiunge `home_coordinates` e `work_coordinates` (lat/lon float) alla response se il geocoding riesce.
- **FR-2:** Il frontend inizializza una mappa Leaflet (OpenStreetMap) nella sezione risultati se le coordinate sono disponibili.
- **FR-3:** Per auto, moto e misto, il frontend chiama OSRM (profilo `driving`) per tracciare il percorso; per bici usa profilo `cycling`; per TP mostra solo marker + nota.
- **FR-4:** La mappa si aggiorna o si reinizializza ad ogni calcolo; si nasconde al reset del form.
- **FR-5:** Il campo `spouse` in `DeductionRequest` è opzionale; se assente, il comportamento è invariato.
- **FR-6:** `SpouseRequest` ha tutti i campi personali del contribuente eccetto `fiscal_year` e `residency_type` (ereditati).
- **FR-7:** Se `spouse.home_address` è null, il backend usa l'indirizzo del contribuente per il coniuge.
- **FR-8:** Il frontend mostra la sezione coniuge solo se la checkbox "Includi coniuge" è spuntata.
- **FR-9:** Il pulsante "Scarica PDF" è sempre visibile dopo il calcolo e genera un PDF senza modifiche.
- **FR-10:** La modalità accertamento rende editabili i valori `amount_chf` nelle tabelle IC e IFD.
- **FR-11:** Il totale IC e IFD si ricalcola in tempo reale quando vengono modificati valori in modalità accertamento.
- **FR-12:** Il PDF accertato non può essere generato senza una motivazione (campo obbligatorio).
- **FR-13:** Il PDF accertato mostra sia i valori originali che quelli accertati, e la motivazione.
- **FR-14:** Nessun dato viene salvato in DB — tutto è stateless (genera e scarica).

---

## Non-Goals (Out of Scope)

- Autenticazione o login per la modalità accertamento.
- Salvataggio delle modifiche del tassatore in database.
- Invio del PDF per email dall'applicazione.
- Calcolo della distanza tramite la mappa (la mappa è solo visiva).
- Rotte per mezzi pubblici (API TP non hanno routing gratuito affidabile).
- Più di un coniuge/partner per dichiarazione.
- Calcolo consolidato (somma contribuente + coniuge) — i risultati rimangono separati.
- Download PDF del coniuge separato dal contribuente (il PDF include entrambi se il coniuge è presente).

---

## Technical Considerations

- **Leaflet**: usare CDN unpkg (1.9.4), già compatibile con il progetto. Gestire il caso in cui la mappa viene reinizializzata (chiamare `.remove()` prima di `new L.Map()`).
- **OSRM**: usare il server demo pubblico `router.project-osrm.org` (gratuito, no API key, limite di fair use). Timeout 3s lato frontend (`AbortController`). Se fallisce, mostrare solo markers.
- **jsPDF**: CDN unpkg (2.5.1), UMD build. Usare `jsPDF.autoTable` (plugin `jspdf-autotable`, stesso CDN) per le tabelle. Aggiungere anche `jspdf-autotable` al CDN.
- **Coordinate nella response**: recuperarle dal geocoder già usato (swisstopo o nominatim); entrambi restituiscono lat/lon. Estrarle dopo la chiamata geocoding in `deduction.py`.
- **SpouseRequest vs DeductionRequest**: evitare di duplicare i validator — estrarre i validator comuni in funzioni helper o usare un mixin se il refactor è contenuto.
- **Retrocompatibilità**: tutti i test esistenti devono passare invariati; `spouse = None` è il default.

---

## Success Metrics

- Dopo il calcolo con indirizzi validi, la mappa appare in meno di 2 secondi.
- Il PDF senza modifiche è scaricabile in un click dopo ogni calcolo.
- Il PDF accertato include tutti i valori modificati e la motivazione, senza perdita di dati.
- Tutti i test esistenti (112+) passano senza regressioni.
- Il campo `spouse` è opzionale: nessuna richiesta esistente rompe il contratto API.

---

## Open Questions

- jsPDF/autotable via CDN: verificare che l'hash di integrità SRI sia disponibile oppure usare senza SRI (accettabile per uso interno).
- OSRM demo server: ha un rate limit non documentato. Se il progetto viene usato intensivamente, valutare una istanza OSRM locale o Nominatim routing in futuro (fuori scope per questa fase).
- La mappa del coniuge: i marker del coniuge sulla mappa del contribuente potrebbero sovraffollare la mappa se gli indirizzi sono molto diversi. Alternativa: due mappe separate (da valutare durante l'implementazione — preferire un'unica mappa se possibile).
