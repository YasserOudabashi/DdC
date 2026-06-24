"""Security layer — rate limiting, API key, security headers."""
from __future__ import annotations

import secrets

from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import settings

# ─── Rate Limiter ─────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

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
    return response
