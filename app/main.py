from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from starlette.responses import JSONResponse

from app.api.v1.router import router
from app.config import settings
from app.security import (
    BodySizeLimitMiddleware,
    add_security_headers,
    limiter,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="DdC Trasferta Service",
    description=(
        "Web Service per il calcolo delle deduzioni fiscali per spese di trasferta "
        "casa-lavoro — Canton Ticino (Art. 25 LT) e IFD (Art. 26 LIFD)."
    ),
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─── Rate limiter ─────────────────────────────────────────────────────────────
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        {"detail": f"Troppe richieste — limite: {settings.rate_limit_per_minute}/min per IP"},
        status_code=429,
    )

# ─── Body size limit ──────────────────────────────────────────────────────────
app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_size_bytes)

# ─── CORS ─────────────────────────────────────────────────────────────────────
origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

# ─── Security headers ─────────────────────────────────────────────────────────
app.middleware("http")(add_security_headers)

# ─── Static files & root ──────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", include_in_schema=False)
async def root():
    return FileResponse("app/static/index.html")


# ─── Router ───────────────────────────────────────────────────────────────────
app.include_router(router)
