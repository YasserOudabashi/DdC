from fastapi import APIRouter
from app.config import settings

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "default_fiscal_year": settings.default_fiscal_year,
        "service": "DdC Trasferta Service",
    }
