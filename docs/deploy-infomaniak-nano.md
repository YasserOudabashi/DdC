# Deploy su Infomaniak VPS Nano

API FastAPI — Deduzioni Trasferta TI  
Nessun database, nessuna autenticazione utente, deploy incrementale possibile in qualsiasi fase.

---

## Deploy in fasi: come funziona

Puoi deployare il backend ora (API già completa e testata) e aggiungere il frontend in seguito. I due componenti sono indipendenti:

| Fase | Cosa deployare | Quando |
|------|----------------|--------|
| Adesso | Solo API FastAPI (backend) | Subito — è già pronto |
| Dopo fase 6 | Frontend web | Quando sarà sviluppato |

Il frontend chiamerà l'API via HTTP — puoi anche tenerli su macchine separate.

---

## Requisiti

- Account Infomaniak attivo
- VPS Nano ordinato (Ubuntu 24.04 LTS — sceglilo al momento dell'ordine)
- Accesso SSH configurato
- Il repo con il codice (cartella `002_Applicativo/`)

---

## 1. Ordina il VPS Nano su Infomaniak

1. Vai su **manager.infomaniak.com** → Cloud → Cloud Server
2. Piano: **Nano** (~CHF 5–6/mese, 1 vCPU, 512MB–1GB RAM)
3. Sistema operativo: **Ubuntu 24.04 LTS**
4. Attiva l'accesso SSH con chiave pubblica (incolla la tua `~/.ssh/id_rsa.pub`)
5. Nota l'indirizzo IP pubblico assegnato (es. `185.xxx.xxx.xxx`)

---

## 2. Primo accesso e setup base

```bash
ssh root@<IP-VPS>

# Aggiorna il sistema
apt update && apt upgrade -y

# Installa Docker
apt install -y docker.io
systemctl enable docker
systemctl start docker
```

---

## 3. Carica il codice sul server

**Opzione A — con git (raccomandato se il repo è su GitHub/GitLab):**
```bash
apt install -y git
git clone <URL-REPO> /opt/trasferta
```

**Opzione B — con scp dalla tua macchina locale:**
```powershell
# Esegui dalla tua macchina Windows
scp -r "D:\006-Documenti\Lavori\DdC\002_Applicativo" root@<IP-VPS>:/opt/trasferta
```

---

## 4. Configura il file .env

```bash
cd /opt/trasferta

# Copia il template
cp .env.example .env

# Edita con nano
nano .env
```

Valori minimi da impostare per la produzione:

```env
DEFAULT_FISCAL_YEAR=2026
LOG_LEVEL=INFO

# Genera un token sicuro e incollalo qui:
# python3 -c "import secrets; print(secrets.token_urlsafe(32))"
API_KEY=metti-qui-il-token-generato

RATE_LIMIT_PER_MINUTE=30
ALLOWED_ORIGINS=https://ddc.ch
MAX_BODY_SIZE_BYTES=1048576
```

> **Nota su API_KEY:** se lasci vuoto, l'API è pubblica. Per uso interno/privato imposta sempre un token.

---

## 5. Build e avvio del container Docker

```bash
cd /opt/trasferta

# Build dell'immagine
docker build -t trasferta-api .

# Test rapido — verifica che risponda
docker run --rm -p 8000:8000 --env-file .env trasferta-api &
curl http://localhost:8000/v1/health
# Risposta attesa: {"status":"ok","default_fiscal_year":2026,"service":"DdC Trasferta Service"}

# Ferma il test
kill %1
```

---

## 6. Avvio automatico con systemd

Crea il file del servizio:

```bash
cat > /etc/systemd/system/trasferta-api.service << 'EOF'
[Unit]
Description=DdC Trasferta API
After=docker.service
Requires=docker.service

[Service]
Restart=always
ExecStartPre=-/usr/bin/docker stop trasferta-api
ExecStartPre=-/usr/bin/docker rm trasferta-api
ExecStart=/usr/bin/docker run --name trasferta-api \
  -p 127.0.0.1:8000:8000 \
  --env-file /opt/trasferta/.env \
  trasferta-api
ExecStop=/usr/bin/docker stop trasferta-api

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable trasferta-api
systemctl start trasferta-api
systemctl status trasferta-api
```

> Il container è esposto solo su `127.0.0.1:8000` (non pubblico) — nginx farà da proxy davanti.

---

## 7. nginx + HTTPS con Let's Encrypt

```bash
apt install -y nginx certbot python3-certbot-nginx

# Crea il virtual host
cat > /etc/nginx/sites-available/trasferta << 'EOF'
server {
    listen 80;
    server_name api.ddc.ch;  # sottodominio API

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOF

ln -s /etc/nginx/sites-available/trasferta /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# Certificato SSL gratuito
certbot --nginx -d api.ddc.ch
```

Dopo certbot, nginx gestisce automaticamente il redirect HTTP→HTTPS e il rinnovo del certificato.

---

## 8. Verifica finale

```bash
# Health check pubblico
curl https://api.ddc.ch/v1/health

# Test calcolo (esempio auto privata 20 km)
curl -X POST https://api.ddc.ch/v1/deduction/calculate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <il-tuo-token>" \
  -d '{
    "fiscal_year": 2026,
    "transport_mode": "private_car",
    "override_distance_km": 20.0,
    "work_days_per_week": 5,
    "home_office_days_per_week": 0
  }'
```

---

## Aggiornamento del codice

Quando rilasci una nuova versione:

```bash
cd /opt/trasferta
git pull                          # o riscp i file
docker build -t trasferta-api .   # rebuild
systemctl restart trasferta-api   # riavvio a caldo (~2 secondi di downtime)
```

---

## Riepilogo costi

| Voce | Costo |
|------|-------|
| VPS Nano Infomaniak | ~CHF 5–6/mese |
| Dominio (opzionale) | ~CHF 10/anno |
| Certificato SSL | Gratuito (Let's Encrypt) |
| **Totale** | **~CHF 5–6/mese** |
