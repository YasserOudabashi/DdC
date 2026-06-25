from fastapi import APIRouter
from .endpoints import deduction, health
from .endpoints.locations import router as locations_router

router = APIRouter(prefix="/v1")
router.include_router(health.router, tags=["health"])
router.include_router(deduction.router, tags=["deduction"])
router.include_router(locations_router, prefix="/locations", tags=["Locations"])
