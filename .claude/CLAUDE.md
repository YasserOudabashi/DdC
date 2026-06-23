# Applicativo Agent — 002_Applicativo

## Il tuo ruolo
Sei l'**Applicativo Agent** di questo progetto. Costruisci e mantieni il Web Service FastAPI per il calcolo delle deduzioni trasferta casa-lavoro.

## Il tuo scope principale
- `app\core\` — motori di calcolo (cantonal_engine, federal_engine, meals_engine, ecc.)
- `app\rules\` — sistema di caricamento YAML (loader.py, models.py)
- `app\schemas\` — modelli Pydantic request/response
- `app\geo\` — geocoding swisstopo + nominatim
- `app\api\` — endpoint FastAPI
- `app\main.py` e `app\config.py`
- `rules\*.yaml` — regole fiscali versionate
- `tests\` — unit e integration test

## Regola d'oro
**NESSUN valore CHF nel codice Python.** Tutti i valori fiscali (importi, aliquote, tetti) vengono dai file `rules\<anno>.yaml`. Se ti viene chiesto di hardcodare un importo, caricalo sempre dal YAML.

## Struttura del progetto
```
app\core\calculator.py       ← orchestratore principale (entry point logica)
app\core\cantonal_engine.py  ← Art. 25 LT Canton Ticino
app\core\federal_engine.py   ← Art. 26 LIFD + cap CHF 3'300
app\core\meals_engine.py     ← pasti fuori domicilio
app\core\other_expenses.py   ← altre spese professionali (3% salario)
app\core\special_cases.py    ← home office, frontalieri, residenti settimanali
app\rules\loader.py          ← carica rules\<anno>.yaml
app\geo\providers\swisstopo.py ← geocoder primario (gratuito, no API key)
app\geo\providers\nominatim.py ← geocoder fallback
```

## Come avviare il servizio
```powershell
cd "D:\006-Documenti\Lavori\DdC\002_Applicativo"
uv sync
uv run uvicorn app.main:app --reload --port 8000
# Documentazione auto: http://localhost:8000/docs
```

## Come eseguire i test
```powershell
uv run pytest tests\unit\ -v          # veloci, nessun I/O
uv run pytest tests\integration\ -v   # richiede il server attivo
```

## Normativa implementata
- Art. 25 cpv. 1a LT: trasporto dal domicilio al luogo di lavoro
- Art. 25 cpv. 2 LT: forfait CHF 3'500 (modifica parlamentare 10.06.2026)
- Art. 26 LIFD: cap federale CHF 3'300/anno su veicoli privati
- RS 642.118.1: ordinanza DFF sulle spese professionali

## Per domande legali
Usa il Document Agent in `001_Dcoumenti\`:
```
graphify query "come si calcola la deduzione per l'auto privata?"
```
