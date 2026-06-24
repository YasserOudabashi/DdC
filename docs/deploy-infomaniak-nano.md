# Deploy su Infomaniak VPS Nano

API FastAPI + Frontend Web — Deduzioni Trasferta TI  
Nessun database, nessuna autenticazione utente.

---

## Il dominio è obbligatorio?

**No.** Il servizio funziona subito all'indirizzo IP del VPS: `http://179.x.x.x:8000`

Il dominio (CHF ~10/anno su Infomaniak) è utile solo per due motivi:
- Avere un URL leggibile (`https://trasferta.tuo-dominio.ch`)
- Ottenere HTTPS via Let's Encrypt (richiede un nome dominio)

Per uso interno o di test, l'IP + porta basta. Per uso pubblico o professionale, un dominio `.ch` è consigliato ma non obbligatorio.

| Scenario | Costo extra | Cosa si perde |
|----------|-------------|---------------|
| Solo IP (`http://IP:8000`) | CHF 0 | Nessun HTTPS, URL brutto |
| Con dominio + HTTPS | ~CHF 10/anno | Niente |

---

## Requisiti

- Account Infomaniak attivo
- VPS Nano ordinato (Ubuntu 24.04 LTS)
- Accesso SSH configurato
- Il repo con il codice (GitHub: `YasserOudabashi/DdC`, privato)

---

## 1. Ordina il VPS Nano su Infomaniak

1. Vai su **manager.infomaniak.com** → Cloud → Cloud Server
2. Piano: **Nano** (~CHF 5–6/mese, 1 vCPU, 512MB–1GB RAM)
3. Sistema operativo: **Ubuntu 24.04 LTS**
4. Attiva l'accesso SSH con chiave pubblica:
   ```powershell
   ssh-keygen -t ed25519 -C "tua@email.com"
   cat C:\Users\<utente>\.ssh\id_ed25519.pub
   ```
   Incolla il contenuto nel campo SSH durante l'ordine.
5. Nota l'**indirizzo IP pubblico** assegnato (es. `179.237.81.123`)
6. L'utente predefinito è **`ubuntu`** (non root)

---

## 2. Primo accesso e setup base

```bash
ssh ubuntu@<IP-VPS>

sudo apt update && sudo apt upgrade -y

# Docker
sudo apt install -y docker.io git
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu
newgrp docker
```

---

## 3. Carica il codice sul server

Il repo è privato — usa un **Personal Access Token** GitHub:

1. GitHub → Settings → Developer settings → Personal access tokens (classic)
2. "Generate new token" → spunta `repo` → copia il token

```bash
git clone https://<USERNAME>:<TOKEN>@github.com/YasserOudabashi/DdC /opt/trasferta
cd /opt/trasferta/002_Applicativo
```

---

## 4. Configura il file .env

```bash
cp .env.example .env
nano .env
```

Valori minimi per la produzione:

```env
DEFAULT_FISCAL_YEAR=2026
LOG_LEVEL=INFO
DOCS_ENABLED=false

# Genera un token sicuro:
# python3 -c "import secrets; print(secrets.token_urlsafe(32))"
API_KEY=metti-qui-il-token-generato

RATE_LIMIT_PER_MINUTE=30

# Senza dominio: usa l'IP
ALLOWED_ORIGINS=http://<IP-VPS>:8000
# Con dominio: ALLOWED_ORIGINS=https://tuo-dominio.ch

MAX_BODY_SIZE_BYTES=1048576
NOMINATIM_CONTACT_EMAIL=tua@email.com
```

> **ALLOWED_ORIGINS=\*** non usarlo mai in produzione: permetterebbe a qualsiasi sito web di chiamare la tua API.

---

## 5. Correggi il Dockerfile per la build su server

Il Dockerfile locale copia `.venv` dalla macchina di sviluppo — sul server non esiste.
Va sostituito con un `uv sync` reale (il server ha internet, la macchina di sviluppo in sandbox no).

```bash
nano /opt/trasferta/002_Applicativo/Dockerfile
```

Trova questa riga:
```dockerfile
COPY .venv/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
```

Sostituiscila con:
```dockerfile
RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"
```

Poi builda l'immagine:
```bash
cd /opt/trasferta/002_Applicativo
docker build -t trasferta-api .
```

Test rapido:
```bash
docker run --rm -p 8000:8000 --env-file .env trasferta-api &
sleep 3
curl http://localhost:8000/v1/health
# Risposta: {"status":"ok","default_fiscal_year":2026,"service":"DdC Trasferta Service"}
kill %1
```

---

## 6. Avvio automatico con systemd

```bash
sudo tee /etc/systemd/system/trasferta-api.service << 'EOF'
[Unit]
Description=DdC Trasferta API
After=docker.service
Requires=docker.service

[Service]
Restart=always
ExecStartPre=-/usr/bin/docker stop trasferta-api
ExecStartPre=-/usr/bin/docker rm trasferta-api
ExecStart=/usr/bin/docker run --name trasferta-api \
  -p 0.0.0.0:8000:8000 \
  --env-file /opt/trasferta/002_Applicativo/.env \
  trasferta-api
ExecStop=/usr/bin/docker stop trasferta-api

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable trasferta-api
sudo systemctl start trasferta-api
sudo systemctl status trasferta-api
```

Il frontend è incluso nel container — apri `http://<IP-VPS>:8000` nel browser e hai già il sito.

---

## 7. Verifica finale

```bash
# Sito web
curl -I http://<IP-VPS>:8000/
# Risposta: HTTP/1.1 200 OK, Content-Type: text/html

# Health check
curl http://<IP-VPS>:8000/v1/health

# Test calcolo con API key
curl -X POST http://<IP-VPS>:8000/v1/deduction/calculate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <il-tuo-token>" \
  -d '{
    "fiscal_year": 2026,
    "residency_type": "resident_TI",
    "transport_mode": "public_transport",
    "annual_public_transport_cost_chf": 1800.0,
    "home_address": {"city": "Lugano", "postal_code": "6900", "country": "CH"},
    "work_address": {"city": "Bellinzona", "postal_code": "6500", "country": "CH"},
    "work_schedule": {"days_per_week": 5, "home_office_days_per_week": 0},
    "include_meals": false
  }'
```

---

## 8. Aggiornamento del codice

```bash
cd /opt/trasferta
git pull
cd 002_Applicativo
docker build -t trasferta-api .
sudo systemctl restart trasferta-api
```

---

## Opzione con dominio + HTTPS (facoltativa)

Se hai un dominio, aggiungi Nginx come reverse proxy per terminare HTTPS:

```bash
sudo apt install -y nginx certbot python3-certbot-nginx

sudo tee /etc/nginx/sites-available/trasferta << 'EOF'
server {
    listen 80;
    server_name tuo-dominio.ch;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/trasferta /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Certificato SSL gratuito
sudo certbot --nginx -d tuo-dominio.ch
```

Poi in `.env`:
```env
ALLOWED_ORIGINS=https://tuo-dominio.ch
TRUSTED_PROXIES=127.0.0.1
DOCS_ENABLED=false
```

Riavvia: `sudo systemctl restart trasferta-api`

---

## Riepilogo costi

| Voce | Costo |
|------|-------|
| VPS Nano Infomaniak | ~CHF 5–6/mese |
| Dominio .ch (opzionale) | ~CHF 10/anno |
| Certificato SSL | Gratuito (Let's Encrypt, solo con dominio) |
| **Totale minimo (solo IP)** | **~CHF 5–6/mese, zero setup extra** |
| **Totale con dominio** | **~CHF 5–6/mese + CHF 10/anno** |
