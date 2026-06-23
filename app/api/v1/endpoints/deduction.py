from fastapi import APIRouter, Depends, HTTPException, Request

from app.schemas.request import DeductionRequest
from app.schemas.response import DeductionResponse
from app.core.calculator import calculate
from app.geo.resolver import resolve_distance
from app.rules.loader import load_rules
from app.security import limiter, verify_api_key
from app.config import settings

router = APIRouter()

_RATE = f"{settings.rate_limit_per_minute}/minute"


@router.post(
    "/deduction/calculate",
    response_model=DeductionResponse,
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit(_RATE)
async def calculate_deduction(request: Request, req: DeductionRequest) -> DeductionResponse:
    try:
        rules = load_rules(req.fiscal_year)
    except FileNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e))

    distance_km: float | None = None
    geocoding_provider: str | None = None

    if req.override_distance_km is None:
        distance_km, geocoding_provider = await resolve_distance(
            req.home_address,
            req.work_address,
            road_factor=rules.geocoding.road_correction_factor,
        )
        if distance_km is None and req.transport_mode.value in ("private_car", "public_transport"):
            raise HTTPException(
                status_code=422,
                detail=(
                    "Impossibile geocodificare gli indirizzi forniti. "
                    "Fornire override_distance_km per procedere senza geocoding."
                ),
            )

    response = await calculate(req, distance_km=distance_km)
    response.geocoding_provider = geocoding_provider
    return response


@router.get(
    "/deduction/rules/{fiscal_year}",
    dependencies=[Depends(verify_api_key)],
)
@limiter.limit(_RATE)
async def get_rules(request: Request, fiscal_year: int) -> dict:
    try:
        rules = load_rules(fiscal_year)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return rules.model_dump()
