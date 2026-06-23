from fastapi import APIRouter
from .endpoints import deduction, health

router = APIRouter(prefix="/v1")
router.include_router(health.router, tags=["health"])
router.include_router(deduction.router, tags=["deduction"])
