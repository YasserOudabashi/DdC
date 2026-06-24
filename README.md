# DdC — Web Service Deduzioni Trasferta TI

API REST in FastAPI per il calcolo automatico delle deduzioni spese di trasporto casa-lavoro, Canton Ticino.

Calcola sia l'**imposta cantonale (IC)** secondo Art. 25 LT che l'**imposta federale diretta (IFD)** secondo Art. 26 LIFD + RS 642.118.1, con supporto completo ai campi del Certificato di Salario (Lohnausweis).

---

## Funzionalità

- **Tutti i mezzi di trasporto:** auto privata, mezzi pubblici, misto (Park & Ride), bicicletta/e-bike, motocicletta targa bianca
- **Casi speciali:** frontalieri CH-IT (accordo 2020), residenti settimanali, home office, turni notturni
- **Lohnausweis:** campo D (trasporto gratuito datore), campo F (mensa aziendale), cifra 13.2.2 (auto aziendale Art. 5a)
- **Multi-anno:** regole 2025 e 2026 (forfait IC CHF 3'500 — modifica parlamentare 10.06.2026)
- **Geocoding:** distanza casa-lavoro calcolata via swisstopo (primario) + OSM Nominatim (fallback)

---

## Avvio rapido

```bash
# Installa le dipendenze
uv sync

# Avvia il server
uv run uvicorn app.main:app --reload --port 8000

# Documentazione interattiva
open http://localhost:8000/docs
```

### Con Docker

```bash
docker build -t trasferta-api .
docker run -p 8000:8000 --env-file .env trasferta-api
```

---

## Esempio di chiamata

```bash
curl -X POST http://localhost:8000/v1/deduction/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "fiscal_year": 2026,
    "transport_mode": "private_car",
    "override_distance_km": 20.0,
    "work_days_per_week": 5,
    "home_office_days_per_week": 0
  }'
```

Risposta (estratto):

```json
{
  "cantonal_TI": {
    "net_deduction_chf": 5280.0,
    "lines": [{ "label": "Auto privata", "net_deduction_chf": 5280.0 }]
  },
  "federal_IFD": {
    "net_deduction_chf": 3300.0,
    "capped": true,
    "lines": [{ "label": "Auto privata (IFD — soggetta a tetto massimo)", "net_deduction_chf": 3300.0 }]
  }
}
```

---

## Endpoint

| Metodo | Path | Descrizione |
|--------|------|-------------|
| `GET` | `/v1/health` | Health check |
| `POST` | `/v1/deduction/calculate` | Calcola le deduzioni |
| `GET` | `/v1/deduction/rules/{fiscal_year}` | Restituisce le regole fiscali per anno |

Specifica OpenAPI completa: [`docs/openapi.json`](docs/openapi.json)

---

## Configurazione

Copia `.env.example` in `.env` e personalizza:

```env
DEFAULT_FISCAL_YEAR=2026
LOG_LEVEL=INFO
API_KEY=                        # vuoto = accesso libero
RATE_LIMIT_PER_MINUTE=30
ALLOWED_ORIGINS=https://api.ddc.ch
```

---

## Test

```bash
uv run pytest tests/unit/ -v          # 68 test, nessun I/O
uv run pytest tests/integration/ -v   # usa ASGITransport
```

---

## Normativa implementata

| Norma | Contenuto |
|-------|-----------|
| Art. 25 LT (RS-TI 640.100) | Spese professionali IC — Canton Ticino |
| Art. 26 LIFD (RS 642.11) | Spese professionali IFD — cap CHF 3'300 |
| RS 642.118.1 | Ordinanza DFF: CHF 0.75/km auto, 0.40 moto, 700 bici |
| RS 0.642.045.43 | Accordo CH-IT frontalieri (firmato 23.12.2020, in vigore 17.07.2023) |

---

## Struttura

```
app/
├── core/
│   ├── calculator.py        ← orchestratore principale
│   ├── cantonal_engine.py   ← Art. 25 LT
│   ├── federal_engine.py    ← Art. 26 LIFD + cap CHF 3'300
│   ├── meals_engine.py      ← pasti fuori domicilio
│   ├── other_expenses.py    ← altre spese 3% salario
│   └── special_cases.py     ← frontalieri, settimanali, HO
├── rules/
│   ├── 2025.yaml            ← regole fiscali 2025
│   └── 2026.yaml            ← regole fiscali 2026
└── schemas/                 ← modelli Pydantic request/response
```

> Nessun valore CHF è hardcodato nel codice Python — tutto viene dai file `rules/*.yaml`.
