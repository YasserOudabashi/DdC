# Diario lavori

Tracciamento incrementale di cosa è stato aggiunto / tolto al progetto, sessione per sessione.
Da rileggere all'inizio di ogni nuova sessione per ricordare lo stato precedente.

## 2026-06-24

### Aggiunto
- `scripts/generate_cost_estimate_docx.py` — script Python che genera un documento Word con la stima di costi e tempi per realizzare l'applicativo a opera di un junior developer (stato attuale + 4 fasi roadmap futura). Usa `python-docx`.
- `docs/stima-junior-developer.docx` — output dello script: documento Word di 38 KB con breakdown attività, tempistiche e range di costo (CHF lower-bound junior interno, upper-bound junior esterno).

### Note
- `python-docx 1.2.0` installato a livello utente con `pip install --user python-docx` (non aggiunto a `pyproject.toml` perché è una dipendenza solo per lo script di reportistica, non per il servizio).
- Il file di piano della roadmap (`quali-prossime-funyionalit-a-potrei-wiggly-matsumoto.md`) vive in `~/.claude/plans/`, non nel repo. Il `.docx` cita il path nelle note.
- Bug 401 sul VPS Infomaniak diagnosticato: il frontend (`app/static/js/app.js`) non invia `X-API-Key`, ma il server (`app/security.py`) lo richiede se `API_KEY` è impostato nel `.env`. Fix proposto: svuotare `API_KEY=""` nel `.env` del VPS e riavviare `trasferta-api`. Nessuna modifica al codice.

### Installazioni esterne (fuori dal repo)
- Skill `/prd` e `/ralph` da [snarktank/ralph](https://github.com/snarktank/ralph) installate manualmente in `~/.claude/plugins/marketplaces/claude-plugins-official/plugins/session-report/skills/prd/SKILL.md` e `…/skills/ralph/SKILL.md`. Le versioni esistenti mancavano della proprietà `user-invocable: true` nel frontmatter. Richiede restart di Claude Code per attivarsi.

### Aggiunto (PRD roadmap)
- `tasks/prd-roadmap-trasferta-api.md` — PRD completo generato con la skill `/prd` a partire da `docs/quali-prossime-funyionalit-a-potrei-wiggly-matsumoto.md`. Copre tutte e 4 le fasi (Audit log SQLite, Export PDF, Multi-cantone ZH/BE, OCR Lohnausweis). User story granulari (US-101…US-406) pensate per esecuzione autonoma con Ralph, ordinate per dipendenza.
- Dipendenze esterne marcate come blocker: **DEP-A** (valori legali ufficiali ZH/BE forniti via YAML + skill legali dell'utente) e **DEP-B** (fixture PDF Lohnausweis anonimizzate per i test OCR).

### Non toccato
- Nessuna modifica al codice dell'applicativo (`app/`, `tests/`, `rules/`).
- Nessuna modifica alla configurazione di deploy.
