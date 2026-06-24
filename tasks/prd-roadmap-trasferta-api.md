# PRD: Roadmap di prodotto — DdC Trasferta API

## Introduction/Overview

Il servizio FastAPI per il calcolo delle deduzioni trasferta casa-lavoro (Canton Ticino + IFD) ha raggiunto maturità tecnica: motori di calcolo completi, supporto multi-anno (2025/2026), campi Lohnausweis (D, F, cifra 11, cifra 13.2.2), geocoding swisstopo+Nominatim, frontend statico minimale e hardening di sicurezza chiuso (93/93 test).

Questo PRD definisce le **prossime 4 fasi di prodotto** che ampliano l'uso reale del servizio:

1. **Audit log persistente** — tracciabilità fiscale di ogni calcolo.
2. **Export PDF del calcolo** — artefatto consegnabile al consulente fiscale.
3. **Estensione altri Cantoni** — da TI-only a multi-cantone (prima ZH e BE).
4. **OCR Lohnausweis upload** — pre-compilazione automatica da scansione del certificato di salario.

**Regola d'oro invariata:** nessun valore CHF nel codice Python — tutti gli importi, aliquote e tetti continuano a vivere nei file `rules/*.yaml`.

Il PRD è scritto per essere eseguito da Claude Code tramite il sistema autonomo **Ralph**: le user story sono volutamente piccole, ordinate per dipendenza, e ciascuna è completabile in una sessione focalizzata con criteri di accettazione verificabili.

## Goals

- Salvare ogni calcolo riuscito su uno store persistente, abilitando rigenerazione successiva e debug post-mortem.
- Generare un PDF stampabile (A4, 1-2 pagine) con input, tutte le `DeductionLine`, riferimenti legali e totali.
- Trasformare il motore cantonale da single-canton (TI) a multi-cantone parametrico, con ZH e BE come prima estensione, senza regressioni sul TI.
- Estrarre automaticamente i campi rilevanti del Lohnausweis da PDF/immagine per ridurre l'input manuale.
- Mantenere zero valori fiscali hardcoded in Python: ogni nuovo dato legale (incluse le `legal_reference` per cantone) passa dai file YAML.
- Non introdurre dipendenze inutili (Fase 1 e 3 a zero nuove dipendenze).

## Sequenza e dipendenze

```
Fase 1 ── Audit log persistente ──┐
                                  ├──► Fase 2 — Export PDF (riusa lo store audit)
Fase 3 ── Altri Cantoni ──────────┘   (può rigenerare report di calcoli storici)

Fase 4 ── OCR Lohnausweis (indipendente, ortogonale)
```

- **Fase 1 prima**: blocco più piccolo, sblocca la rigenerazione PDF da `request_id`; `app/audit/` è già un placeholder vuoto.
- **Fase 2 subito dopo**: riusa lo schema `DeductionResponse` esistente — basso rischio, valore immediato.
- **Fase 3 in parallelo o dopo**: refactor più invasivo (tocca `cantonal_engine`, `calculator`, `rules/models`, YAML, schema). Da non incrociare con altre modifiche al motore.
- **Fase 4 per ultima**: la più speculativa (dipende da qualità scansioni), dipendenze pesanti. Spedibile separatamente.

## Dipendenze esterne fornite dall'utente

Queste sono **precondizioni** alle relative user story; non vanno inventate:

- **DEP-A (Fase 3):** valori fiscali e `legal_reference` ufficiali per ZH e BE (trasporto + pasti) — l'utente fornirà un file YAML con tutti i dati e/o skill dedicate per la parte legale. Finché non disponibili, le story che richiedono valori reali ZH/BE restano bloccate; la struttura del codice e i test parametrizzati possono procedere con fixture provvisorie.
- **DEP-B (Fase 4):** fixture PDF reali del Lohnausweis (anonimizzate): almeno un testuale moderno, un testuale vecchio, una scansione immagine. Finché non disponibili, parser e modelli si sviluppano su fixture sintetiche minime.

---

## User Stories

> Convenzione: ogni story termina con typecheck/lint + test della story. Le story marcate **[bloccata da DEP-x]** richiedono i dati esterni sopra prima del completamento finale.

### Fase 1 — Audit log persistente

#### US-101: Definire lo schema record dell'audit
**Description:** As a developer, I want a Pydantic/dataclass model del record di audit so that lo store ha una forma dati stabile e tipizzata.

**Acceptance Criteria:**
- [ ] Nuovo file `app/audit/models.py` con modello `AuditRecord` contenente: `request_id: str`, `calculated_at: datetime`, `fiscal_year: int`, `canton: str`, `input_hash: str`, `request_payload: str` (JSON), `response_payload: str` (JSON), `geocoding_provider: str | None`, `distance_km: float | None`.
- [ ] L'indirizzo home è memorizzato nel payload in forma offuscata: solo `postal_code` + `city`, mai `street` (riduzione PII).
- [ ] `input_hash` è un hash deterministico (es. sha256) del payload di input normalizzato.
- [ ] Typecheck/lint passa.

#### US-102: Interfaccia astratta dello store di audit
**Description:** As a developer, I want un protocol `AuditStore` so that l'endpoint dipende da un'astrazione e in futuro si può cambiare backend (Postgres) senza toccare l'API.

**Acceptance Criteria:**
- [ ] In `app/audit/store.py` un `AuditStore` Protocol con metodi `save(record: AuditRecord) -> None` e `get(request_id: str) -> AuditRecord | None`.
- [ ] Nessuna dipendenza dal framework FastAPI nel protocol.
- [ ] Typecheck/lint passa.

#### US-103: Implementazione SQLite dello store
**Description:** As a developer, I want un'implementazione SQLite via `sqlite3` (stdlib) so that l'audit persiste senza nuove dipendenze.

**Acceptance Criteria:**
- [ ] `SQLiteAuditStore` in `app/audit/store.py` implementa `AuditStore`.
- [ ] Crea la tabella `calculations` al primo uso se mancante (schema allineato a `AuditRecord`).
- [ ] `request_id` è PRIMARY KEY (idempotenza: una seconda `save` con stesso id non duplica e non solleva eccezione non gestita).
- [ ] Usa solo `sqlite3` stdlib — **nessuna nuova dipendenza in `pyproject.toml`**.
- [ ] Typecheck/lint passa.

#### US-104: Configurazione audit
**Description:** As an operator, I want flag di configurazione so that posso abilitare/disabilitare l'audit e scegliere il path del DB.

**Acceptance Criteria:**
- [ ] In `app/config.py`: `audit_enabled: bool = True` e `audit_db_path: str = "audit.db"`, sovrascrivibili via env var.
- [ ] Con `audit_enabled=False` nessuna scrittura avviene e nessun errore viene sollevato.
- [ ] Typecheck/lint passa.

#### US-105: Salvataggio del calcolo dopo il calculate
**Description:** As a user, I want che ogni calcolo riuscito venga registrato so that è tracciabile e rigenerabile.

**Acceptance Criteria:**
- [ ] In `app/api/v1/endpoints/deduction.py`, dopo `calculate()`, si invoca `store.save()` costruendo l'`AuditRecord` dalla request/response.
- [ ] Lo store è iniettato come dipendenza FastAPI (non istanziato inline nell'handler), rispettando `audit_enabled`.
- [ ] Un fallimento dello store **non** fa fallire la response del calcolo (best-effort, logga e prosegue).
- [ ] Il `request_id` salvato coincide con `DeductionResponse.request_id`.
- [ ] Typecheck/lint passa.

#### US-106: Endpoint di lettura audit
**Description:** As a user, I want `GET /v1/audit/{request_id}` so that posso ricaricare un calcolo storico.

**Acceptance Criteria:**
- [ ] Nuovo `app/api/v1/endpoints/audit.py` con `GET /v1/audit/{request_id}`, registrato nel router v1.
- [ ] Restituisce il payload salvato (request offuscata + response) per un id esistente.
- [ ] Restituisce 404 per un id inesistente.
- [ ] Typecheck/lint passa.

#### US-107: Test di integrazione audit
**Description:** As a developer, I want test end-to-end so that il ciclo salva→rileggi è garantito.

**Acceptance Criteria:**
- [ ] Nuovo `tests/integration/test_audit.py`: POST `/v1/deduction/calculate`, estrae `request_id`, GET `/v1/audit/{request_id}` e verifica coincidenza payload.
- [ ] Test che con `audit_enabled=False` non avviene scrittura e l'endpoint calculate funziona comunque.
- [ ] Test idempotenza: due calcoli con stesso input non corrompono lo store.
- [ ] `uv run pytest tests/integration/test_audit.py -v` passa.

---

### Fase 2 — Export PDF del calcolo

#### US-201: Modulo reports e renderer
**Description:** As a developer, I want un modulo di rendering PDF so that la generazione è isolata e testabile.

**Acceptance Criteria:**
- [ ] Nuovo `app/reports/__init__.py` e `app/reports/pdf_renderer.py` con `render_deduction_pdf(response: DeductionResponse, request: DeductionRequest) -> bytes`.
- [ ] La funzione non accede a rete né filesystem se non per i template.
- [ ] Typecheck/lint passa.

#### US-202: Aggiunta dipendenza WeasyPrint
**Description:** As a developer, I want la libreria di rendering so that posso produrre PDF da HTML/CSS.

**Acceptance Criteria:**
- [ ] `weasyprint` aggiunto a `pyproject.toml` e `uv sync` completa su Windows.
- [ ] Nota nel README/LAVORI sul fallback `reportlab` se WeasyPrint dà friction in produzione Windows.
- [ ] Typecheck/lint passa.

#### US-203: Template HTML print-friendly
**Description:** As a tax consultant, I want un layout pulito A4 so that il documento è leggibile e stampabile.

**Acceptance Criteria:**
- [ ] Nuovo `app/reports/templates/deduction.html` (Jinja2) con CSS `@page { size: A4; margin: 1.5cm }`.
- [ ] Sezioni: intestazione, dati input principali (indirizzi offuscati come da audit, `transport_mode`, `residency_type`, `fiscal_year`, `canton`), tabella `DeductionLine` cantonali e federali con `basis` e `legal_reference`, totale per livello, blocco `warnings` se presenti.
- [ ] Tutte le `legal_reference` provengono da `DeductionLine.legal_reference` (nessun hardcoding nel template).
- [ ] Typecheck/lint passa.

#### US-204: Endpoint export PDF
**Description:** As a user, I want `GET /v1/deduction/{request_id}/pdf` so that scarico il PDF di un calcolo salvato.

**Acceptance Criteria:**
- [ ] Endpoint recupera il calcolo via `audit_store.get(request_id)` (dipende da Fase 1), renderizza e risponde con `content-type: application/pdf`.
- [ ] 404 se il `request_id` non esiste nell'audit store.
- [ ] In assenza di audit (`audit_enabled=False`), il PDF resta ottenibile solo via POST con body completo (documentato).
- [ ] Typecheck/lint passa.

#### US-205: Test di integrazione export PDF
**Description:** As a developer, I want test so that l'output è un PDF valido.

**Acceptance Criteria:**
- [ ] Nuovo `tests/integration/test_pdf_export.py`: POST calculate, GET PDF, verifica `content-type: application/pdf` e che i primi byte siano `%PDF-`.
- [ ] Verifica che il PDF non sia vuoto (dimensione > soglia minima).
- [ ] `uv run pytest tests/integration/test_pdf_export.py -v` passa.
- [ ] Verifica manuale del layout A4 (margini, tabelle, riferimenti legali leggibili).

---

### Fase 3 — Estensione altri Cantoni (ZH, BE)

#### US-301: Spostare le legal_reference cantonali nel YAML (TI)
**Description:** As a developer, I want le `legal_reference` di trasporto/pasti/altre lette dal YAML so that diventano per-cantone senza hardcoding.

**Acceptance Criteria:**
- [ ] In `rules/2025.yaml` e `rules/2026.yaml` ogni regola cantonale rilevante ha un campo `legal_reference`.
- [ ] `app/core/cantonal_engine.py` legge la `legal_reference` dal YAML invece di stringhe hardcoded (es. "Art. 25 cpv. 1 lett. a LT").
- [ ] **Regressione zero**: i test TI esistenti continuano a passare invariati.
- [ ] Typecheck/lint passa.

#### US-302: Modello rules multi-cantone
**Description:** As a developer, I want un mapping cantone→regole so that più cantoni coesistono.

**Acceptance Criteria:**
- [ ] `app/rules/models.py`: la sezione cantonale diventa `cantonal: dict[str, CantonalRules]` (chiavi `TI`, `ZH`, `BE`, ...) — decisione finale tra dict-mapping e `CantonRules` con campo `canton` documentata nel codice.
- [ ] Modello retrocompatibile: il caricamento del TI continua a funzionare.
- [ ] Typecheck/lint passa.

#### US-303: Loader YAML multi-cantone
**Description:** As a developer, I want il loader che legge la sezione `cantonal:` con sotto-chiavi so that ogni cantone ha il suo blocco.

**Acceptance Criteria:**
- [ ] `app/rules/loader.py` supporta `cantonal:` con sotto-chiavi `TI`/`ZH`/`BE`.
- [ ] YAML `2025.yaml`/`2026.yaml` ristrutturati con la sezione cantonale annidata, **mantenendo i valori TI esistenti**.
- [ ] I test di caricamento TI esistenti passano.
- [ ] Typecheck/lint passa.

#### US-304: Cantonal engine parametrico per cantone
**Description:** As a developer, I want `cantonal_engine` che riceve `canton: str` so that calcola con le regole del cantone richiesto.

**Acceptance Criteria:**
- [ ] `app/core/cantonal_engine.py`: sostituire l'accesso fisso `rules.cantonal_TI` con selezione `rules.cantonal[canton]`.
- [ ] Errore esplicito e chiaro se il cantone richiesto non esiste nel YAML dell'anno.
- [ ] Typecheck/lint passa.

#### US-305: Propagazione canton in calculator e schema
**Description:** As a user, I want indicare il cantone nella request so that ricevo il calcolo del cantone giusto.

**Acceptance Criteria:**
- [ ] `app/schemas/request.py`: aggiungere `canton: CantonCode = "TI"` (enum TI/ZH/BE), default TI per retrocompatibilità.
- [ ] `app/core/calculator.py`: propaga `canton` da `DeductionRequest`; `level` diventa `f"cantonal_{canton}"`.
- [ ] `app/schemas/response.py`: `TaxLevelResult.level` accetta i nuovi valori; aggiungere `canton: str` esplicito.
- [ ] Richieste senza `canton` continuano a comportarsi come TI (regressione zero).
- [ ] Typecheck/lint passa.

#### US-306: Dati YAML ZH e BE **[bloccata da DEP-A]**
**Description:** As a tax user, I want le regole reali ZH e BE nel YAML so that i calcoli per quei cantoni sono corretti.

**Acceptance Criteria:**
- [ ] In `rules/2026.yaml` blocchi `ZH` e `BE` per **trasporto e pasti** con valori CHF e `legal_reference` dalle fonti ufficiali fornite dall'utente (DEP-A: file YAML + skill legali).
- [ ] Nessun valore inventato: ogni numero è tracciabile alla fonte fornita.
- [ ] Scope prima iterazione: solo trasporto e pasti (altre spese / alloggio settimanale rimandati).
- [ ] Typecheck/lint passa.

#### US-307: Test parametrizzati multi-cantone
**Description:** As a developer, I want test su TI/ZH/BE so that la correttezza per cantone è garantita.

**Acceptance Criteria:**
- [ ] `tests/unit/test_cantonal_engine.py` parametrizzato su `canton`; casi ZH e BE su input identici producono risultati coerenti con i rispettivi YAML.
- [ ] Test di integrazione: `POST /v1/deduction/calculate` con `"canton":"ZH"` restituisce `level: "cantonal_ZH"` e usa il YAML 2026 ZH.
- [ ] (Se esiste endpoint rules) `GET /v1/deduction/rules/2026?canton=ZH` ritorna solo la sezione ZH.
- [ ] `uv run pytest tests/unit/ -v` passa senza regressioni TI.

---

### Fase 4 — OCR Lohnausweis upload

#### US-401: Modello dei campi estratti
**Description:** As a developer, I want un modello dei campi Lohnausweis so that l'estrazione ha output strutturato.

**Acceptance Criteria:**
- [ ] Nuovo `app/ocr/models.py` con `LohnausweisFields` Pydantic: `field_d_checked: bool | None`, `field_f_checked: bool | None`, `annual_net_salary_chf: float | None`, `company_car_monthly_chf: float | None`, `confidence_score: float` (0-1).
- [ ] Stessi vincoli di `DeductionRequest` sui campi numerici (es. `>= 0`).
- [ ] Typecheck/lint passa.

#### US-402: Parser PDF testuale
**Description:** As a user, I want estrarre i campi da un Lohnausweis PDF digitale so that non li reinserisco a mano.

**Acceptance Criteria:**
- [ ] Nuovo `app/ocr/__init__.py` e `app/ocr/lohnausweis_parser.py` con `parse_lohnausweis(file_bytes: bytes, mime_type: str) -> LohnausweisFields`.
- [ ] `pdfplumber` aggiunto a `pyproject.toml`; estrazione per coordinate sul layout standard BFS (campi D, F, cifra 11, cifra 13.2.2).
- [ ] Il file **non** viene mai persistito su disco (privacy); solo il risultato strutturato è prodotto.
- [ ] Ogni campo riceve un contributo al `confidence_score`.
- [ ] Typecheck/lint passa.

#### US-403: Fallback OCR immagine (opzionale)
**Description:** As a user, I want estrarre i campi anche da scansioni immagine so that funziona con PDF non testuali.

**Acceptance Criteria:**
- [ ] Se il PDF non è testuale, fallback opzionale via `pytesseract` (Tesseract installato lato server — documentato nel deploy).
- [ ] Se Tesseract non è disponibile, il parser ritorna `confidence_score` basso senza crash.
- [ ] Typecheck/lint passa.

#### US-404: Endpoint upload parse
**Description:** As a user, I want `POST /v1/lohnausweis/parse` so that carico il file e ricevo i campi.

**Acceptance Criteria:**
- [ ] Nuovo `app/api/v1/endpoints/upload.py` con `POST /v1/lohnausweis/parse` (`UploadFile`), registrato nel router.
- [ ] Risponde con JSON `LohnausweisFields` (campi + confidence).
- [ ] Caso negativo: un PDF generico (non Lohnausweis) ritorna `confidence_score` basso e nessun campo riconosciuto, senza crash.
- [ ] Typecheck/lint passa.

#### US-405: Endpoint composto calculate-from-lohnausweis (opzionale)
**Description:** As a user, I want `POST /v1/deduction/calculate-from-lohnausweis` so that in una chiamata carico e calcolo.

**Acceptance Criteria:**
- [ ] Endpoint che combina parse + completamento manuale dei campi mancanti (indirizzi, distanza) + `calculate`.
- [ ] I campi estratti con confidence sotto soglia richiedono valore esplicito dal client (non assunti).
- [ ] Typecheck/lint passa.

#### US-406: Test parser OCR **[bloccata da DEP-B]**
**Description:** As a developer, I want test su fixture reali so that l'estrazione è affidabile.

**Acceptance Criteria:**
- [ ] `tests/unit/test_ocr_parser.py` + fixture in `tests/fixtures/`: almeno 3 campioni (testuale moderno, testuale vecchio, scansione) forniti dall'utente (DEP-B), anonimizzati.
- [ ] Estrazione corretta dei 4 campi sui campioni testuali; confidence coerente sulla scansione.
- [ ] Test caso negativo (PDF non Lohnausweis).
- [ ] `uv run pytest tests/unit/test_ocr_parser.py -v` passa.

---

### Fase 0 — Tracciamento lavori (preferenza utente)

#### US-001: Creare e mantenere il file di tracciamento
**Description:** As the user, I want un file `.md` di tracciamento in `G:\DdC\` so that prima di ogni sessione so cosa è stato fatto.

**Acceptance Criteria:**
- [ ] Esiste `LAVORI.md` in `G:\DdC\` (già presente come bozza), aggiornato dopo ogni fase con: data, fase chiusa, file aggiunti/modificati, eventuale migrazione YAML.
- [ ] Va riletto all'inizio di ogni sessione e aggiornato alla fine.

---

## Functional Requirements

- FR-1: Il sistema deve salvare ogni calcolo riuscito in uno store persistente con chiave `request_id`, se `audit_enabled=True`.
- FR-2: Lo store di audit deve offuscare l'indirizzo home (solo `postal_code`+`city`, mai `street`).
- FR-3: Il sistema deve esporre `GET /v1/audit/{request_id}` per recuperare un calcolo salvato (404 se assente).
- FR-4: Un errore dello store di audit non deve mai far fallire la response del calcolo.
- FR-5: Il sistema deve generare un PDF A4 da una `DeductionResponse`+`DeductionRequest`, con tutte le `DeductionLine`, `basis`, `legal_reference`, totali e warnings.
- FR-6: Il sistema deve esporre `GET /v1/deduction/{request_id}/pdf` (recupero dall'audit store).
- FR-7: Tutte le `legal_reference` nel PDF e nei calcoli devono provenire dai dati (YAML/schema), mai hardcoded in Python.
- FR-8: Il sistema deve accettare `canton` nella request (enum TI/ZH/BE, default TI) e calcolare con le regole del cantone scelto.
- FR-9: Le regole cantonali (valori CHF + `legal_reference`) devono vivere nei file `rules/*.yaml` per cantone.
- FR-10: Le richieste senza `canton` devono comportarsi esattamente come oggi (TI) — regressione zero.
- FR-11: Il sistema deve estrarre da un Lohnausweis (PDF testuale o immagine) i campi D, F, cifra 11, cifra 13.2.2 con un `confidence_score` per campo.
- FR-12: Il file caricato per OCR non deve mai essere persistito su disco.
- FR-13: L'OCR su un documento non riconosciuto deve ritornare confidence bassa senza crash.
- FR-14: Fase 1 e Fase 3 non devono introdurre nuove dipendenze runtime.

## Non-Goals (Out of Scope)

- Nessun TTL/purge automatico o retention policy sull'audit log.
- Nessun backend di audit diverso da SQLite in questa iterazione (solo astrazione predisposta).
- Nessuna UI/frontend nuova per audit o PDF (solo API; il frontend statico resta invariato).
- Fase 3: nessun supporto per cantoni oltre TI/ZH/BE; nessuna copertura di altre spese/alloggio settimanale per ZH/BE in prima iterazione.
- Fase 4: nessun salvataggio del file caricato; nessuna correzione automatica/AI dei campi a bassa confidence.
- Nessun valore CHF o aliquota hardcoded in Python in nessuna fase.

## Technical Considerations

- **Audit**: `sqlite3` stdlib; store dietro un Protocol per futura sostituibilità; iniettato come dipendenza FastAPI.
- **PDF**: WeasyPrint (HTML+CSS→PDF) con Jinja2; fallback documentato a `reportlab` se friction su Windows.
- **Multi-cantone**: refactor invasivo — eseguire prima la migrazione YAML + spostamento `legal_reference` e verificare regressione zero TI, poi parametrizzare l'engine.
- **OCR**: `pdfplumber` per PDF testuali (layout BFS standard, coordinate predicibili); `pytesseract` opzionale per scansioni (richiede Tesseract sul server).
- **Idempotenza audit**: PRIMARY KEY su `request_id` (già generato in `app/schemas/response.py`).
- **Esecuzione Ralph**: le story sono ordinate per dipendenza; quelle marcate [bloccata da DEP-x] vanno saltate finché i dati esterni non sono disponibili.

## Success Metrics

- 100% dei calcoli riusciti tracciati nell'audit quando abilitato; ciclo salva→rileggi verificato dai test.
- PDF generato valido (`%PDF-`) per ogni calcolo, con tutte le DeductionLine e riferimenti legali presenti.
- Calcoli TI invariati al bit dopo il refactor multi-cantone (suite test pre-esistente verde).
- Calcoli ZH/BE coerenti con i valori ufficiali forniti.
- Estrazione corretta dei 4 campi Lohnausweis su ≥ 2/3 dei campioni testuali; nessun crash sul caso negativo.
- Zero nuove dipendenze in Fase 1 e Fase 3.

## Open Questions

- **DEP-A:** quali sono le fonti/valori ufficiali ZH (StGB ZH) e BE (StG BE) per trasporto e pasti 2026? In che forma arriverà il YAML/skill?
- **DEP-B:** disponibilità dei 3 campioni Lohnausweis anonimizzati per le fixture OCR.
- Modello rules multi-cantone: `dict[str, CantonalRules]` vs `CantonRules` con campo `canton` — decisione da confermare in US-302.
- WeasyPrint vs reportlab: confermare WeasyPrint funzioni in produzione Windows prima di consolidare la dipendenza.
- Soglia di `confidence_score` sotto la quale un campo OCR richiede conferma manuale.
- Esiste già un endpoint `GET /v1/deduction/rules/...`? Verificare prima di US-307.
