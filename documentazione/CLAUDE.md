# documentazione/ — Documentazione tecnica del progetto

Questa cartella contiene documentazione in formato .docx sul progetto nel suo complesso: come è stato pensato, come sta venendo realizzato, le scelte tecniche fatte.

## Contenuto attuale

- `Analisi_IT_WebService_DdC.docx` — analisi tecnica del web service (struttura API, endpoint, logica di calcolo)

## Cosa aggiungere qui

Documenti .docx che spiegano l'evoluzione e le scelte del progetto, diversi dall'analisi tecnica già presente:

- **Come è stato pensato:** contesto del problema (deduzioni trasferta TI), perché un web service JSON, chi sono gli utenti previsti
- **Come sta venendo realizzato:** stack tecnologico (FastAPI, uv, pytest, Docker, ralph), struttura delle fasi, pattern PRD→ralph→git
- **Decisioni architetturali:** perché i valori CHF nei YAML e non nel codice, perché motori cantonale/federale separati, perché graphify per la normativa
- **Guida all'integrazione:** come chiamare l'API, esempi di request/response, casi d'uso tipici (frontalieri, auto aziendale, mensa)

## Nota

Non duplicare le informazioni già in `002_Applicativo/.claude/CLAUDE.md` (istruzioni per l'agente) o in `001_Dcoumenti/` (normativa fiscale). Questo spazio è per documentazione orientata allo sviluppatore umano o a un futuro integratore esterno.
