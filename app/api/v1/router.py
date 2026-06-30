from fastapi import APIRouter
from .endpoints import deduction, health, route
from .endpoints.locations import router as locations_router

router = APIRouter(prefix="/v1")
router.include_router(health.router, tags=["health"])
router.include_router(deduction.router, tags=["deduction"])
router.include_router(route.router, tags=["route"])
router.include_router(locations_router, prefix="/locations", tags=["Locations"])
