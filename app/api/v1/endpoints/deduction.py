import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request

from app.schemas.request import DeductionRequest, TransportMode
from app.schemas.response import DeductionLine, DeductionResponse, TransportResult
from app.core.calculator import calculate
from app.geo.resolver import resolve_distance
from app.geo import tp_proximity
from app.rules.loader import load_rules
from app.security import limiter, verify_api_key
from app.config import settings

router = APIRouter()

_RATE = f"{settings.rate_limit_per_minute}/minute"

_TP_THRESHOLD_M = 200.0
_MAX_CAR_KM = 30.0


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
    home_coords: tuple[float, float] | None = None
    work_coords: tuple[float, float] | None = None

    if req.override_distance_km is None:
        distance_km, geocoding_provider, home_coords, work_coords = await resolve_distance(
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

    if req.transport_mode == TransportMode.PRIVATE_CAR:
        blocked_reason = await _check_car_eligibility(
            req, distance_km, home_coords, work_coords
        )
        if blocked_reason:
            _apply_car_block(response, blocked_reason)
    elif home_coords is not None:
        # Avviso informativo: fermata TP vicina (modalità non-auto)
        nearby = await tp_proximity.find_nearest_stop(home_coords[0], home_coords[1])
        if nearby is not None:
            stop_name, dist_m = nearby
            if dist_m <= _TP_THRESHOLD_M:
                response.warnings.append(
                    f"Fermata TP '{stop_name}' a {dist_m:.0f}m dal domicilio — "
                    "valutare deduzione per mezzi pubblici (Art. 25 LT)"
                )

    return response


async def _check_car_eligibility(
    req: DeductionRequest,
    distance_km: float | None,
    home_coords: tuple[float, float] | None,
    work_coords: tuple[float, float] | None,
) -> str | None:
    """
    Ritorna il motivo del blocco se la deduzione auto non è ammessa, altrimenti None.

    Regola 1 (geocoding only): fermata TP entro 200m dal domicilio e/o luogo di lavoro.
    Regola 2 (geocoding only): distanza casa-lavoro < 30 km.
    Entrambe si applicano solo quando la distanza proviene dal geocoder
    (override_distance_km=None), perché è la situazione in cui abbiamo le coordinate.
    """
    home_stop: tuple[str, float] | None = None
    work_stop: tuple[str, float] | None = None

    if home_coords and work_coords:
        home_stop, work_stop = await asyncio.gather(
            tp_proximity.find_nearest_stop(home_coords[0], home_coords[1]),
            tp_proximity.find_nearest_stop(work_coords[0], work_coords[1]),
        )
    elif home_coords:
        home_stop = await tp_proximity.find_nearest_stop(home_coords[0], home_coords[1])
    elif work_coords:
        work_stop = await tp_proximity.find_nearest_stop(work_coords[0], work_coords[1])

    home_ok = home_stop is not None and home_stop[1] <= _TP_THRESHOLD_M
    work_ok = work_stop is not None and work_stop[1] <= _TP_THRESHOLD_M

    if home_ok and work_ok:
        h_name, h_dist = home_stop  # type: ignore[misc]
        w_name, w_dist = work_stop  # type: ignore[misc]
        return (
            f"I mezzi pubblici sono raggiungibili a piedi sia dal domicilio "
            f"(fermata '{h_name}' a {h_dist:.0f}m) sia dal luogo di lavoro "
            f"(fermata '{w_name}' a {w_dist:.0f}m): "
            "il trasporto pubblico poteva essere utilizzato, quindi la deduzione "
            "per auto privata non è ammessa (Art. 25 cpv. 1a LT / Art. 26 LIFD)."
        )
    if home_ok:
        h_name, h_dist = home_stop  # type: ignore[misc]
        return (
            f"Fermata TP '{h_name}' a {h_dist:.0f}m dal domicilio: "
            "i mezzi pubblici sono accessibili a piedi, quindi la deduzione "
            "per auto privata non è ammessa (Art. 25 cpv. 1a LT / Art. 26 LIFD). "
            "Poteva essere utilizzato il trasporto pubblico."
        )
    if work_ok:
        w_name, w_dist = work_stop  # type: ignore[misc]
        return (
            f"Fermata TP '{w_name}' a {w_dist:.0f}m dal luogo di lavoro: "
            "i mezzi pubblici sono accessibili a piedi, quindi la deduzione "
            "per auto privata non è ammessa (Art. 25 cpv. 1a LT / Art. 26 LIFD). "
            "Poteva essere utilizzato il trasporto pubblico."
        )

    # Regola 30km: solo se la distanza proviene dal geocoder (non da override manuale)
    if req.override_distance_km is None and distance_km is not None and distance_km < _MAX_CAR_KM:
        return (
            f"Distanza casa-lavoro {distance_km:.1f} km (inferiore a 30 km): "
            "per percorsi di questa lunghezza i mezzi pubblici sono considerati "
            "ragionevolmente utilizzabili; la deduzione per auto privata non è ammessa "
            "(Art. 25 cpv. 1a LT / Art. 26 LIFD). "
            "Poteva essere utilizzato il trasporto pubblico."
        )

    return None


def _apply_car_block(response: DeductionResponse, reason: str) -> None:
    """Azzera la deduzione trasporto auto privata e aggiunge il motivo come avvertenza."""
    blocked_line = DeductionLine(
        label="Deduzione auto privata non ammessa",
        amount_chf=0.0,
        basis=reason,
        legal_reference="Art. 25 cpv. 1a LT / Art. 26 LIFD",
    )
    for level in [response.cantonal_TI, response.federal_IFD]:
        orig = level.transport_deduction
        if orig.net_deduction_chf == 0.0:
            continue  # già azzerato (es. Campo D Lohnausweis)
        delta = orig.net_deduction_chf
        level.transport_deduction = TransportResult(
            mode=orig.mode,
            one_way_distance_km=orig.one_way_distance_km,
            effective_working_days=orig.effective_working_days,
            gross_deduction_chf=orig.gross_deduction_chf,
            net_deduction_chf=0.0,
            lines=[blocked_line],
        )
        if not level.flat_rate_applied:
            level.total_deduction_chf = round(level.total_deduction_chf - delta, 2)
    response.warnings.append(reason)


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
