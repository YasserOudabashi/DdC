# Security

## Dependency audit

Verifica le dipendenze per CVE note:

```bash
uv run pip-audit
```

Deve terminare con exit code 0 (zero vulnerabilità). Eseguire prima di ogni deploy.

## Security headers

Il middleware `add_security_headers` in `app/security.py` imposta:

- `Content-Security-Policy` — limita le origini di script, stili e font
- `Strict-Transport-Security` — forza HTTPS per 1 anno
- `X-Frame-Options: DENY` — blocca l'embedding in iframe
- `X-Content-Type-Options: nosniff`
- `Permissions-Policy` — disabilita geolocation, camera, microfono
- `Referrer-Policy: strict-origin-when-cross-origin`

## API key

Se `API_KEY` è impostata in `.env`, ogni richiesta a `/v1/deduction/calculate` e `/v1/deduction/rules/{year}` richiede l'header `X-API-Key`. Il confronto è timing-safe (`secrets.compare_digest`).

Genera un token sicuro:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Rate limiting

Default: 30 req/minuto per IP. Configurabile con `RATE_LIMIT_PER_MINUTE` in `.env`.

Dietro un reverse proxy (Nginx), impostare `TRUSTED_PROXIES=127.0.0.1` affinché il rate limiting legga l'IP reale dal header `X-Forwarded-For`.
