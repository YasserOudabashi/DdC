"""Security layer — rate limiting, API key, security headers."""
from __future__ import annotations

import secrets

from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import settings

# ─── Rate Limiter ─────────────────────────────────────────────────────────────

def get_real_ip(request: Request) -> str:
    """Return the real client IP, honouring X-Forwarded-For for trusted proxies."""
    trusted = [ip.strip() for ip in settings.trusted_proxies.split(",") if ip.strip()]
    client_host = request.client.host if request.client else None
    if client_host and client_host in trusted:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=get_real_ip)

# ─── API Key ──────────────────────────────────────────────────────────────────
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Security(_api_key_header)) -> None:
    if not settings.api_key:
        return  # nessuna chiave configurata → accesso libero
    if not secrets.compare_digest(api_key or "", settings.api_key or ""):
        raise HTTPException(status_code=401, detail="API key mancante o non valida")


# ─── Body Size Guard ──────────────────────────────────────────────────────────
class BodySizeLimitMiddleware:
    """Rifiuta richieste con body superiore a max_body_size_bytes."""

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            content_length = headers.get(b"content-length")
            if content_length and int(content_length) > self.max_bytes:
                from starlette.responses import JSONResponse
                response = JSONResponse(
                    {"detail": f"Body troppo grande (max {self.max_bytes // 1024} KB)"},
                    status_code=413,
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


# ─── Security Headers ─────────────────────────────────────────────────────────
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' https://fonts.googleapis.com https://unpkg.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "script-src 'self' https://unpkg.com; "
        "img-src 'self' data: https://*.tile.openstreetmap.org; "
        "connect-src 'self' https://unpkg.com https://router.project-osrm.org "
        "https://transport.opendata.ch https://api3.geo.admin.ch https://openplzapi.org; "
        "frame-ancestors 'none'"
    )
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    return response
