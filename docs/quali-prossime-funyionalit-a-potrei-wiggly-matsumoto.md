# Roadmap prossime funzionalità — DdC Trasferta API

## Context

Il servizio FastAPI è arrivato a maturità tecnica: motori di calcolo TI+IFD completi, supporto multi-anno (2025/2026), Lohnausweis (campi D, F, 11, 13.2.2), geocoding swisstopo+Nominatim, frontend statico minimale, hardening di sicurezza chiuso (93/93 test, fase 7). Mancano funzionalità di **prodotto** che amplino l'uso reale: tracciabilità dei calcoli, artefatti consegnabili al consulente fiscale, copertura geografica oltre il TI, e riduzione dell'input manuale.

L'utente ha scelto di affrontare **tutte e 4** le direzioni come roadmap sequenziale anziché feature singole. Questo piano definisce ordine, dipendenze, scope e verifiche per ciascuna fase, mantenendo intatta la regola d'oro del progetto: **nessun valore CHF nel codice Python** — tutto continua a venire dai file `rules/*.yaml`.

---

## Sequenza consigliata e dipendenze

```
Fase 1 ── Audit log persistente ──┐
                                  ├──► Fase 2 — Export PDF (riusa lo stato salvato)
Fase 3 ── Altri Cantoni ──────────┘   (può rigenerare report di calcoli storici)
                                  
Fase 4 ── OCR Lohnausweis (indipendente, ortogonale)
```

**Razionale dell'ordine:**
- **Audit prima** perché è il blocco più piccolo, sblocca rigenerazione PDF da request_id, e la cartella `app/audit/` è già un placeholder vuoto pronto.
- **Export PDF subito dopo** perché riusa lo schema `DeductionResponse` esistente — basso rischio, valore immediato per l'utente finale.
- **Altri Cantoni in parallelo o dopo** perché è il refactor più invasivo (tocca `cantonal_engine`, `calculator`, `rules/models`, YAML, response schema) — meglio non incrociarlo con altre modifiche al motore.
- **OCR per ultimo** perché è la più speculativa (dipende dalla qualità delle scansioni reali) e introduce dipendenze pesanti (es. pdfplumber + parsing visivo). Spedibile separatamente senza bloccare le altre tre.

---

## Fase 1 — Audit log persistente

### Obiettivo
Salvare ogni calcolo riuscito su uno store persistente per tracciabilità fiscale, debug post-mortem e abilitare la rigenerazione successiva di report PDF da `request_id`.

### File chiave
- `app/audit/__init__.py` — oggi vuoto, diventa il modulo
- `app/audit/store.py` — nuovo: interfaccia astratta + implementazione SQLite
- `app/audit/models.py` — nuovo: schema record (request_id, calculated_at, fiscal_year, input_hash, request_payload, response_payload, geocoding_provider, distance_km)
- `app/api/v1/endpoints/deduction.py` — aggiungere chiamata `store.save()` dopo `calculate()` (~riga 47)
- `app/api/v1/endpoints/audit.py` — nuovo endpoint `GET /v1/audit/{request_id}` per ricaricare un calcolo
- `app/config.py` — aggiungere `audit_enabled: bool = True` e `audit_db_path: str = "audit.db"`
- `tests/integration/test_audit.py` — nuovo

### Approccio
- **Backend**: SQLite via `sqlite3` stdlib (no nuove dipendenze), file `audit.db` configurabile.
- **Privacy**: salvare l'indirizzo home in forma offuscata (solo postal_code + city, non street) per ridurre superficie PII; la response completa va salvata come JSON serializzato.
- **Idempotenza**: chiave primaria su `request_id` (già generato in `DeductionResponse.request_id` — `app/schemas/response.py:40`).
- **Astrazione**: il modulo espone `AuditStore` protocol per consentire in futuro Postgres/altro senza toccare l'endpoint.
- **Retention**: NON aggiungere TTL/purge automatico — non richiesto e introduce complessità.

### Verifica
1. `uv run pytest tests/integration/test_audit.py -v` — il test fa POST `/v1/deduction/calculate`, legge il `request_id` dalla risposta, poi GET `/v1/audit/{request_id}` e verifica che restituisca lo stesso payload.
2. Manualmente: avviare il servizio, fare 3 calcoli diversi via Swagger, verificare che `audit.db` contenga 3 righe (`sqlite3 audit.db "SELECT request_id, fiscal_year, calculated_at FROM calculations"`).
3. Verificare che con `audit_enabled=False` (env var) nessuna scrittura avvenga e nessun errore venga sollevato.

---

## Fase 2 — Export PDF del calcolo

### Obiettivo
Generare un PDF stampabile (1-2 pagine A4) con: intestazione, dati input principali, tutte le `DeductionLine` cantonali e federali con `basis` e `legal_reference`, totale per livello, eventuali `warnings`. Consegnabile a un consulente fiscale come documentazione del calcolo.

### File chiave
- `app/reports/__init__.py` — nuovo modulo
- `app/reports/pdf_renderer.py` — nuovo: funzione `render_deduction_pdf(response: DeductionResponse, request: DeductionRequest) -> bytes`
- `app/reports/templates/deduction.html` — nuovo: template Jinja2 con CSS print-friendly
- `app/api/v1/endpoints/deduction.py` — aggiungere endpoint `GET /v1/deduction/{request_id}/pdf` che recupera dall'audit store + renderizza
- `tests/integration/test_pdf_export.py` — nuovo
- `pyproject.toml` — aggiungere `weasyprint` (o `reportlab`) come dipendenza

### Approccio
- **Libreria**: WeasyPrint (HTML+CSS→PDF, controllo tipografico fine, no dipendenze native su Windows con wheel ufficiali recenti). Fallback `reportlab` se WeasyPrint introduce friction su Windows in produzione.
- **Template**: Jinja2 (già transitiva via FastAPI/Starlette). HTML semantico + CSS dedicato per la stampa con `@page { size: A4; margin: 1.5cm }`.
- **Dati**: il template riceve la `DeductionResponse` completa + un sottoinsieme della `DeductionRequest` (indirizzi, transport_mode, residency_type) per intestazione.
- **Riferimenti legali**: già presenti in ogni `DeductionLine.legal_reference` (`app/schemas/response.py:12`). Niente hardcoding aggiuntivo.
- **Dipendenza Fase 1**: l'endpoint recupera il calcolo via `audit_store.get(request_id)`. Senza audit, il PDF si può solo ottenere come POST con request body completo.

### Verifica
1. `uv run pytest tests/integration/test_pdf_export.py -v` — POST per generare un calcolo, GET del PDF, verifica `content-type: application/pdf` e che il primo header del PDF sia `%PDF-`.
2. Manualmente: dopo un POST calculate, aprire `/v1/deduction/{request_id}/pdf` nel browser, verificare layout, presenza di tutte le DeductionLine, riferimenti legali leggibili.
3. Stampare/PDF preview su carta A4 per controllare margini e impaginazione.

---

## Fase 3 — Estensione altri Cantoni

### Obiettivo
Passare da "TI-only" a configurazione multi-cantone, aggiungendo come prima estensione **Zurigo (ZH)** e **Berna (BE)**. La scelta del cantone arriva dal request body; le regole vivono in YAML separati come oggi per il TI.

### File chiave (refactoring più invasivo)
- `app/rules/models.py` — rinominare `cantonal_TI: CantonalRules` in mapping `cantonal: dict[str, CantonalRules]` o introdurre `CantonRules` con campo `canton: str`. Decidere durante implementazione.
- `app/rules/loader.py` — supportare struttura YAML con sezione `cantonal:` che contiene sotto-chiavi `TI`, `ZH`, `BE`, ecc.
- `rules/2025.yaml`, `rules/2026.yaml` — ristrutturare le sezioni cantonali; aggiungere `rules/2026.yaml` blocchi `ZH` e `BE` con valori reali da fonti ufficiali (StGB ZH, StG BE).
- `app/core/cantonal_engine.py` — sostituire `r = rules.cantonal_TI` (riga 21) con parametro `canton: str`; tutte le `legal_reference` ("Art. 25 cpv. 1 lett. a LT") vanno spostate in YAML perché dipendono dal cantone.
- `app/core/calculator.py` — propagare `canton` da `DeductionRequest`; rinominare `level="cantonal_TI"` (riga 89) in `level=f"cantonal_{canton}"`.
- `app/schemas/request.py` — aggiungere `canton: CantonCode = "TI"` (enum con TI, ZH, BE).
- `app/schemas/response.py` — `TaxLevelResult.level` accetta i nuovi valori; aggiungere `canton: str` esplicito.
- `tests/unit/test_cantonal_engine.py` — parametrizzare i test esistenti su canton, aggiungere casi ZH/BE.

### Approccio
- **Backward compatibility**: default `canton="TI"` mantiene il comportamento attuale; richieste esistenti continuano a funzionare.
- **Legal references in YAML**: aggiungere campo `legal_reference` per ogni regola di trasporto/pasti/altre nel YAML. Il motore lo legge invece di hardcodarlo. Questo è il refactor più delicato — fare una migrazione `rules/2026.yaml` prima e verificare che i test esistenti TI continuino a passare.
- **Fonti per ZH/BE**: prima di codificare valori CHF, l'utente fornisce le fonti ufficiali (Steueramt cantonale) — o si delega al Document Agent (`001_Dcoumenti\` via `graphify query`). Questo piano NON impone valori specifici, solo la struttura.
- **Scope ridotto in prima iterazione**: ZH+BE solo per trasporto e pasti. Altre spese, secondaria, alloggio settimanale: rimandate a iterazione successiva se hanno regole molto diverse.

### Verifica
1. `uv run pytest tests/unit/ -v` — i test esistenti TI continuano a passare invariati (regressione zero).
2. Nuovi test in `test_cantonal_engine.py` con casi ZH e BE su input identici: i risultati devono differire dai TI in modo coerente con le regole YAML caricate.
3. `POST /v1/deduction/calculate` con `"canton": "ZH"` restituisce `level: "cantonal_ZH"` e il YAML 2026 ZH è effettivamente usato.
4. `GET /v1/deduction/rules/2026?canton=ZH` ritorna solo la sezione ZH.

---

## Fase 4 — OCR Lohnausweis upload

### Obiettivo
Endpoint che accetta un PDF/immagine del Certificato di Salario svizzero ed estrae i campi rilevanti (D, F, cifra 11, cifra 13.2.2) per pre-compilare la `DeductionRequest`. Riduce drasticamente l'input manuale.

### File chiave
- `app/ocr/__init__.py` — nuovo modulo
- `app/ocr/lohnausweis_parser.py` — nuovo: funzione `parse_lohnausweis(file_bytes: bytes, mime_type: str) -> LohnausweisFields`
- `app/ocr/models.py` — nuovo: `LohnausweisFields` Pydantic con campi opzionali (`field_d_checked`, `field_f_checked`, `annual_net_salary_chf`, `company_car_monthly_chf`, `confidence_score`)
- `app/api/v1/endpoints/upload.py` — nuovo: `POST /v1/lohnausweis/parse` con `UploadFile`
- `tests/unit/test_ocr_parser.py` + fixture PDF di test in `tests/fixtures/`
- `pyproject.toml` — aggiungere `pdfplumber` per PDF testuali; `pytesseract` opzionale per scansioni immagine

### Approccio
- **Doppia strategia**:
  1. Se il PDF è "testuale" (generato digitalmente), `pdfplumber` estrae testo per coordinate — il Lohnausweis ufficiale ha layout standardizzato BFS, quindi le coordinate dei campi D/F/cifra-11/cifra-13.2.2 sono predicibili.
  2. Se il PDF è una scansione immagine, fallback opzionale Tesseract OCR via `pytesseract` (richiede Tesseract installato sul server — documentare nel deploy).
- **No salvataggio**: il file non viene mai persistito su disco (privacy). Solo il risultato strutturato torna al client.
- **Confidence score**: ogni campo estratto ha un punteggio 0-1; il client decide se accettare o chiedere conferma manuale all'utente.
- **Validazione**: i campi estratti passano attraverso `LohnausweisFields` Pydantic con stessi vincoli di `DeductionRequest` (es. `annual_net_salary_chf >= 0`).
- **Endpoint composto opzionale**: `POST /v1/deduction/calculate-from-lohnausweis` che combina upload + calculate in una chiamata.

### Verifica
1. `uv run pytest tests/unit/test_ocr_parser.py -v` con fixture PDF reali (anonimizzati) — verifica estrazione corretta su almeno 3 campioni: testuale moderno, testuale vecchio, scansione.
2. `POST /v1/lohnausweis/parse` con un file di test → riceve JSON con campi popolati e confidence.
3. Manualmente: chain upload→calculate, verificare che il risultato finale combaci con un calcolo manuale fatto inserendo gli stessi valori a mano.
4. Caso negativo: upload di un PDF generico (non Lohnausweis) deve ritornare `confidence_score` basso e nessun campo riconosciuto, senza crash.

---

## Note operative (preferenza utente da CLAUDE.md globale)

L'utente mantiene un file `.md` in ogni cartella di lavoro che traccia cosa è stato aggiunto/tolto, da rileggere prima di ogni sessione. **Oggi questo file non esiste in `G:\DdC\`**. Prima di iniziare la Fase 1 va creato (es. `LAVORI.md` o `CHANGELOG_FEATURES.md`) e aggiornato dopo ogni fase con:
- data
- fase chiusa
- file aggiunti/modificati
- migrazione YAML eventuale

---

## Riepilogo stima sforzo (orientativo)

| Fase | Sforzo | Rischio | Nuove dipendenze |
|------|--------|---------|------------------|
| 1. Audit log SQLite | Basso | Basso | nessuna (stdlib) |
| 2. Export PDF | Medio | Basso | weasyprint |
| 3. Altri Cantoni | Alto | Medio (refactor invasivo + dati legali esterni) | nessuna |
| 4. OCR Lohnausweis | Alto | Alto (qualità OCR variabile) | pdfplumber + (opz.) pytesseract |
