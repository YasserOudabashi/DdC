import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request

from app.schemas.request import Address, DeductionRequest, TransportMode
from app.schemas.response import (
    AddressCheck, Coordinates, DeductionLine, DeductionResponse, TransportResult,
)
from app.core.calculator import build_alternative_transport, calculate, calculate_spouse
from app.geo.resolver import resolve_distance
from app.geo.providers.base import GeoResolved
from app.geo import tp_proximity
from app.rules.loader import load_rules
from app.security import limiter, verify_api_key
from app.config import settings

router = APIRouter()

_RATE = f"{settings.rate_limit_per_minute}/minute"

_TP_THRESHOLD_M = 300.0
_MAX_CAR_KM = 30.0

_ALT_SCENARIO_NOTE = (
    "Scenario alternativo disponibile: 'auto fino alla stazione + abbonamento ARCOBALENO'. "
    "La deduzione auto privata resta azzerata; lo scenario alternativo è indicativo "
    "(zone abbonamento stimate dalla distanza) e può essere rettificato in accertamento."
)


def _normalize_npa(value: str | None) -> str:
    return (value or "").replace(" ", "").strip().lower()


def _validate_npa(field: str, addr: Address, resolved: GeoResolved | None) -> AddressCheck | None:
    """Confronta l'NPA inserito con quello risolto dal geocoder.

    Ritorna None se non ci sono dati risolti (validazione saltata, es. nei test).
    matched=False se l'NPA risolto è presente e diverso da quello inserito.
    """
    if resolved is None or resolved.postcode is None:
        return None
    matched = _normalize_npa(addr.postal_code) == _normalize_npa(resolved.postcode)
    return AddressCheck(
        field=field,
        input_npa=addr.postal_code,
        resolved_npa=resolved.postcode,
        input_city=addr.city,
        resolved_city=resolved.city,
        matched=matched,
    )


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

    # Geocoding sempre eseguito: serve per validare override, controlli TP e auto privata
    (
        geocoded_km, geocoding_provider, home_coords, work_coords,
        home_resolved, work_resolved,
    ) = await resolve_distance(
        req.home_address,
        req.work_address,
        road_factor=rules.geocoding.road_correction_factor,
    )

    if req.override_distance_km is not None:
        if geocoded_km is not None:
            diff = abs(req.override_distance_km - geocoded_km)
            if diff > 5.0:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"La distanza inserita manualmente ({req.override_distance_km:.1f} km) "
                        f"differisce di {diff:.1f} km dalla distanza calcolata automaticamente "
                        f"({geocoded_km:.1f} km). La differenza massima consentita è 5 km. "
                        "Verificare gli indirizzi o la distanza inserita."
                    ),
                )
        distance_km: float | None = req.override_distance_km
        geocoding_provider = f"override (geocodificato: {geocoded_km:.1f} km)" if geocoded_km else "override"
    else:
        distance_km = geocoded_km
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

    # Coordinate geocodificate nel response (US-1001)
    if home_coords is not None:
        response.home_coordinates = Coordinates(lat=home_coords[0], lon=home_coords[1])
    if work_coords is not None:
        response.work_coordinates = Coordinates(lat=work_coords[0], lon=work_coords[1])

    # Validazione NPA ↔ città/via: avvisa + propone la correzione (non blocca)
    for field, addr, resolved in (
        ("home", req.home_address, home_resolved),
        ("work", req.work_address, work_resolved),
    ):
        check = _validate_npa(field, addr, resolved)
        if check is not None:
            response.address_validation.append(check)
            if not check.matched:
                response.warnings.append(
                    f"NPA {addr.postal_code} non corrisponde alla località risolta per "
                    f"{'il domicilio' if field == 'home' else 'il luogo di lavoro'} "
                    f"({check.resolved_npa or '?'} {check.resolved_city or ''}). "
                    f"Verificare l'indirizzo: l'NPA corretto sembra {check.resolved_npa}."
                )

    # Calcolo coniuge/partner (US-1002/1003)
    if req.spouse is not None:
        sp = req.spouse
        spouse_home_addr = sp.home_address if sp.home_address is not None else req.home_address
        (
            sp_km, sp_provider, sp_home_c, sp_work_c, sp_home_resolved, sp_work_resolved,
        ) = await resolve_distance(
            spouse_home_addr,
            sp.work_address,
            road_factor=rules.geocoding.road_correction_factor,
        )

        # Stesse regole del contribuente principale anche per il coniuge:
        # l'override manuale non può discostarsi di oltre 5 km dal geocoding.
        if sp.override_distance_km is not None:
            if sp_km is not None:
                sp_diff = abs(sp.override_distance_km - sp_km)
                if sp_diff > 5.0:
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            f"Coniuge: la distanza inserita manualmente ({sp.override_distance_km:.1f} km) "
                            f"differisce di {sp_diff:.1f} km dalla distanza calcolata automaticamente "
                            f"({sp_km:.1f} km). La differenza massima consentita è 5 km. "
                            "Verificare gli indirizzi o la distanza inserita per il coniuge."
                        ),
                    )
            sp_distance: float | None = sp.override_distance_km
        else:
            sp_distance = sp_km
            if sp_distance is None and sp.transport_mode.value in ("private_car", "public_transport"):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Coniuge: impossibile geocodificare gli indirizzi forniti. "
                        "Fornire la distanza manuale del coniuge per procedere senza geocoding."
                    ),
                )

        sp_geo_used = sp_km is not None and sp.override_distance_km is None
        spouse_result = calculate_spouse(
            main_req=req,
            distance_km=sp_distance,
            home_coords=sp_home_c,
            work_coords=sp_work_c,
            geocoding_used=sp_geo_used,
        )

        # Stessa verifica di ammissibilità auto privata del contribuente (regola 30 km / fermata TP)
        if sp.transport_mode == TransportMode.PRIVATE_CAR:
            sp_blocked, sp_station_km = await _check_car_eligibility(sp, sp_distance, sp_home_c, sp_work_c)
            if sp_blocked:
                # Cattura i giorni effettivi prima dell'azzeramento
                sp_eff_days = spouse_result.cantonal_TI.transport_deduction.effective_working_days
                _apply_car_block_spouse(spouse_result, sp_blocked)
                sp_alt = build_alternative_transport(
                    sp_distance, sp_station_km, sp_eff_days, rules, sp.arcobaleno_class,
                )
                if sp_alt is not None:
                    spouse_result.cantonal_TI.alternative_transport = sp_alt[0]
                    spouse_result.federal_IFD.alternative_transport = sp_alt[1]
                    spouse_result.warnings.append(_ALT_SCENARIO_NOTE)

        # Validazione NPA coniuge
        for sp_field, sp_addr, sp_res in (
            ("spouse_home", spouse_home_addr, sp_home_resolved),
            ("spouse_work", sp.work_address, sp_work_resolved),
        ):
            sp_check = _validate_npa(sp_field, sp_addr, sp_res)
            if sp_check is not None:
                response.address_validation.append(sp_check)

        response.spouse = spouse_result

    if req.transport_mode == TransportMode.PRIVATE_CAR:
        blocked_reason, station_km = await _check_car_eligibility(
            req, distance_km, home_coords, work_coords
        )
        if blocked_reason:
            eff_days = response.cantonal_TI.transport_deduction.effective_working_days
            _apply_car_block(response, blocked_reason)
            alt = build_alternative_transport(
                distance_km, station_km, eff_days, rules, req.arcobaleno_class,
            )
            if alt is not None:
                response.cantonal_TI.alternative_transport = alt[0]
                response.federal_IFD.alternative_transport = alt[1]
                response.warnings.append(_ALT_SCENARIO_NOTE)
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
) -> tuple[str | None, float | None]:
    """
    Ritorna (motivo_blocco, distanza_stazione_km).

    motivo_blocco è il testo dell'avvertenza se la deduzione auto non è ammessa, altrimenti None.
    distanza_stazione_km è la distanza dal domicilio alla fermata più vicina (km), usata
    per costruire lo scenario alternativo "auto fino alla stazione + abbonamento".

    Regola 1 (geocoding only): fermata TP entro 300m dal domicilio e/o luogo di lavoro.
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

    # Distanza (km) per il tratto auto→stazione: fermata più vicina al domicilio.
    if home_stop is not None:
        station_km: float | None = round(home_stop[1] / 1000.0, 2)
    elif work_stop is not None:
        station_km = round(work_stop[1] / 1000.0, 2)
    else:
        station_km = None

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
        ), station_km
    if home_ok:
        h_name, h_dist = home_stop  # type: ignore[misc]
        return (
            f"Fermata TP '{h_name}' a {h_dist:.0f}m dal domicilio: "
            "i mezzi pubblici sono accessibili a piedi, quindi la deduzione "
            "per auto privata non è ammessa (Art. 25 cpv. 1a LT / Art. 26 LIFD). "
            "Poteva essere utilizzato il trasporto pubblico."
        ), station_km
    if work_ok:
        w_name, w_dist = work_stop  # type: ignore[misc]
        return (
            f"Fermata TP '{w_name}' a {w_dist:.0f}m dal luogo di lavoro: "
            "i mezzi pubblici sono accessibili a piedi, quindi la deduzione "
            "per auto privata non è ammessa (Art. 25 cpv. 1a LT / Art. 26 LIFD). "
            "Poteva essere utilizzato il trasporto pubblico."
        ), station_km

    # Regola 30km: solo se la distanza proviene dal geocoder (non da override manuale)
    if req.override_distance_km is None and distance_km is not None and distance_km < _MAX_CAR_KM:
        return (
            f"Distanza casa-lavoro {distance_km:.1f} km (inferiore a 30 km): "
            "per percorsi di questa lunghezza i mezzi pubblici sono considerati "
            "ragionevolmente utilizzabili; la deduzione per auto privata non è ammessa "
            "(Art. 25 cpv. 1a LT / Art. 26 LIFD). "
            "Poteva essere utilizzato il trasporto pubblico."
        ), station_km

    return None, station_km


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


def _apply_car_block_spouse(spouse, reason: str) -> None:
    """Azzera la deduzione auto privata del coniuge e registra il motivo come avvertenza."""
    blocked_line = DeductionLine(
        label="Deduzione auto privata non ammessa",
        amount_chf=0.0,
        basis=reason,
        legal_reference="Art. 25 cpv. 1a LT / Art. 26 LIFD",
    )
    for level in [spouse.cantonal_TI, spouse.federal_IFD]:
        orig = level.transport_deduction
        if orig.net_deduction_chf == 0.0:
            continue
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
    spouse.warnings.append(reason)


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
