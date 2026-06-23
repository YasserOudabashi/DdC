"""
Orchestratore principale — coordina tutti i motori di calcolo.
Chiamato dall'endpoint POST /v1/deduction/calculate.
"""
from __future__ import annotations
from ..schemas.request import DeductionRequest, MealSituation, TransportMode
from ..schemas.response import DeductionLine, DeductionResponse, TaxLevelResult, TransportResult
from ..rules.loader import load_rules
from ..rules.models import FiscalYearRules
from . import cantonal_engine, federal_engine, meals_engine, other_expenses, special_cases


async def calculate(req: DeductionRequest, distance_km: float | None = None) -> DeductionResponse:
    rules = load_rules(req.fiscal_year)

    one_way_km = req.override_distance_km or distance_km
    warnings = special_cases.collect_warnings(req)
    geocoding_used = distance_km is not None and req.override_distance_km is None
    geocoding_provider: str | None = None  # verrà impostato dal resolver

    effective_meal_situation = _resolve_meal_situation(req, warnings)

    cantonal = _build_cantonal(req, one_way_km, rules, effective_meal_situation)
    federal  = _build_federal(req, one_way_km, rules, effective_meal_situation)

    return DeductionResponse(
        fiscal_year=req.fiscal_year,
        rules_version=rules.version,
        cantonal_TI=cantonal,
        federal_IFD=federal,
        geocoding_used=geocoding_used,
        geocoding_provider=geocoding_provider,
        distance_km=one_way_km,
        warnings=warnings,
    )


def _resolve_meal_situation(req: DeductionRequest, warnings: list[str]) -> MealSituation:
    """US-402: campo F Lohnausweis — forza la tariffa ridotta pasti se mensa aziendale disponibile."""
    if not req.employer_has_cafeteria or not req.include_meals:
        return req.meal_situation

    override_map = {
        MealSituation.WITHOUT_CAFETERIA: MealSituation.WITH_CAFETERIA,
        MealSituation.WEEKLY_RESIDENT:   MealSituation.WEEKLY_RESIDENT_WITH_CAFETERIA,
    }
    overridden = override_map.get(req.meal_situation, req.meal_situation)
    if overridden != req.meal_situation:
        warnings.append(
            "CAMPO F: Mensa aziendale disponibile — applicata tariffa ridotta pasti "
            "(CHF 7.50/giorno invece di CHF 15.00/giorno)"
        )
    return overridden


def _build_cantonal(
    req: DeductionRequest, one_way_km: float | None,
    rules: FiscalYearRules, effective_meal_situation: MealSituation,
) -> TaxLevelResult:
    transport = _cantonal_transport(req, one_way_km, rules)

    meals_chf: float | None = None
    if req.include_meals:
        meals_chf = meals_engine.calculate_meals_cantonal(effective_meal_situation, req.work_schedule, rules)

    other_chf: float | None = None
    if req.include_other_expenses and req.annual_net_salary_chf is not None:
        other_chf = other_expenses.calculate_other_cantonal(req.annual_net_salary_chf, rules)

    total = transport.net_deduction_chf + (meals_chf or 0.0) + (other_chf or 0.0)

    flat_rate = rules.cantonal_TI.flat_rate_all_expenses_chf
    flat_rate_applied = False
    if flat_rate is not None and flat_rate > total:
        total = flat_rate
        flat_rate_applied = True

    return TaxLevelResult(
        level="cantonal_TI",
        transport_deduction=transport,
        meals_deduction_chf=meals_chf,
        other_expenses_deduction_chf=other_chf,
        total_deduction_chf=round(total, 2),
        flat_rate_applied=flat_rate_applied,
        flat_rate_chf=flat_rate if flat_rate_applied else None,
        notes=_cantonal_notes(rules),
    )


def _build_federal(
    req: DeductionRequest, one_way_km: float | None,
    rules: FiscalYearRules, effective_meal_situation: MealSituation,
) -> TaxLevelResult:
    transport = _federal_transport(req, one_way_km, rules)

    meals_chf: float | None = None
    if req.include_meals:
        meals_chf = meals_engine.calculate_meals_federal(effective_meal_situation, req.work_schedule, rules)

    other_chf: float | None = None
    if req.include_other_expenses and req.annual_net_salary_chf is not None:
        other_chf = other_expenses.calculate_other_federal(req.annual_net_salary_chf, rules)

    total = transport.net_deduction_chf + (meals_chf or 0.0) + (other_chf or 0.0)

    return TaxLevelResult(
        level="federal_IFD",
        transport_deduction=transport,
        meals_deduction_chf=meals_chf,
        other_expenses_deduction_chf=other_chf,
        total_deduction_chf=round(total, 2),
        notes=_federal_notes(rules),
    )


def _cantonal_transport(
    req: DeductionRequest, one_way_km: float | None, rules: FiscalYearRules,
) -> TransportResult:
    """US-401 + US-403: gestione campo D e cifra 13.2.2 per il livello cantonale."""
    if (
        req.company_car_monthly_chf is not None
        and req.transport_mode == TransportMode.PRIVATE_CAR
    ):
        gross = round(req.company_car_monthly_chf * 12, 2)
        return TransportResult(
            mode="private_car",
            effective_working_days=0,
            gross_deduction_chf=gross,
            net_deduction_chf=gross,
            lines=[DeductionLine(
                label="Auto aziendale — calcolo forfettario (cifra 13.2.2 Lohnausweis)",
                amount_chf=gross,
                basis=f"CHF {req.company_car_monthly_chf:.2f} × 12 mesi (Art. 5a RS 642.118.1)",
                legal_reference="Art. 5a RS 642.118.1",
            )],
        )

    result = cantonal_engine.calculate_transport(
        transport_mode=req.transport_mode,
        one_way_km=one_way_km,
        work_schedule=req.work_schedule,
        rules=rules,
        annual_public_transport_cost_chf=req.annual_public_transport_cost_chf,
        car_distance_km_mixed=req.car_distance_km_mixed,
        public_transport_cost_mixed_chf=req.public_transport_cost_mixed_chf,
    )

    if req.employer_pays_transport:
        return _zero_transport(result)

    return result


def _federal_transport(
    req: DeductionRequest, one_way_km: float | None, rules: FiscalYearRules,
) -> TransportResult:
    """US-401 + US-403: gestione campo D e cifra 13.2.2 per il livello federale."""
    if (
        req.company_car_monthly_chf is not None
        and req.transport_mode == TransportMode.PRIVATE_CAR
    ):
        gross = round(req.company_car_monthly_chf * 12, 2)
        cap = rules.federal_IFD.transport.private_car.cap_chf
        net = round(min(gross, cap), 2) if cap else gross
        capped = cap is not None and gross > cap
        return TransportResult(
            mode="private_car",
            effective_working_days=0,
            gross_deduction_chf=gross,
            net_deduction_chf=net,
            lines=[DeductionLine(
                label="Auto aziendale — calcolo forfettario (cifra 13.2.2 Lohnausweis)",
                amount_chf=net,
                basis=f"CHF {req.company_car_monthly_chf:.2f} × 12 mesi (Art. 5a RS 642.118.1)",
                legal_reference="Art. 5a RS 642.118.1",
                capped=capped,
                cap_amount_chf=cap if capped else None,
            )],
        )

    result = federal_engine.calculate_transport(
        transport_mode=req.transport_mode,
        one_way_km=one_way_km,
        work_schedule=req.work_schedule,
        rules=rules,
        annual_public_transport_cost_chf=req.annual_public_transport_cost_chf,
        car_distance_km_mixed=req.car_distance_km_mixed,
        public_transport_cost_mixed_chf=req.public_transport_cost_mixed_chf,
    )

    if req.employer_pays_transport:
        return _zero_transport(result)

    return result


def _zero_transport(original: TransportResult) -> TransportResult:
    """US-401: campo D spuntato — mantiene il gross teorico ma azzera il net."""
    return TransportResult(
        mode=original.mode,
        one_way_distance_km=original.one_way_distance_km,
        effective_working_days=original.effective_working_days,
        gross_deduction_chf=original.gross_deduction_chf,
        net_deduction_chf=0.0,
        lines=[DeductionLine(
            label="Trasporto a carico del datore di lavoro",
            amount_chf=0.0,
            basis="Campo D Lohnausweis spuntato — nessuna deduzione ammessa",
            legal_reference="Art. 26 cpv. 2 LIFD / Art. 25 cpv. 2 LT",
        )],
    )


def _cantonal_notes(rules: FiscalYearRules) -> list[str]:
    notes = []
    if rules.cantonal_TI.flat_rate_all_expenses_chf:
        notes.append(
            f"Disponibile forfait globale CHF {rules.cantonal_TI.flat_rate_all_expenses_chf:.0f} "
            "(Art. 25 cpv. 2 LT — modifica parlamentare 10.06.2026, verificare entrata in vigore)"
        )
    return notes


def _federal_notes(rules: FiscalYearRules) -> list[str]:
    cap = rules.federal_IFD.transport.private_car.cap_chf
    if cap:
        return [f"Tetto massimo IFD per veicolo privato: CHF {cap:.0f}/anno (RS 642.118.1)"]
    return []
