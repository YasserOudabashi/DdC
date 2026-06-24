from fastapi import APIRouter, Request
from app.config import settings
from app.security import limiter

router = APIRouter()


@router.get("/health")
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def health(request: Request) -> dict:
    return {
        "status": "ok",
        "default_fiscal_year": settings.default_fiscal_year,
        "service": "DdC Trasferta Service",
    }
