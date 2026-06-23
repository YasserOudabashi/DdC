"""
Orchestratore principale — coordina tutti i motori di calcolo.
Chiamato dall'endpoint POST /v1/deduction/calculate.
"""
from __future__ import annotations
from ..schemas.request import DeductionRequest, TransportMode
from ..schemas.response import DeductionResponse, TaxLevelResult
from ..rules.loader import load_rules
from ..rules.models import FiscalYearRules
from . import cantonal_engine, federal_engine, meals_engine, other_expenses, special_cases


async def calculate(req: DeductionRequest, distance_km: float | None = None) -> DeductionResponse:
    rules = load_rules(req.fiscal_year)

    one_way_km = req.override_distance_km or distance_km
    warnings = special_cases.collect_warnings(req)
    geocoding_used = distance_km is not None and req.override_distance_km is None
    geocoding_provider: str | None = None  # verrà impostato dal resolver

    cantonal = _build_cantonal(req, one_way_km, rules)
    federal  = _build_federal(req, one_way_km, rules)

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


def _build_cantonal(req: DeductionRequest, one_way_km: float | None, rules: FiscalYearRules) -> TaxLevelResult:
    transport = cantonal_engine.calculate_transport(
        transport_mode=req.transport_mode,
        one_way_km=one_way_km,
        work_schedule=req.work_schedule,
        rules=rules,
        annual_public_transport_cost_chf=req.annual_public_transport_cost_chf,
        car_distance_km_mixed=req.car_distance_km_mixed,
        public_transport_cost_mixed_chf=req.public_transport_cost_mixed_chf,
    )

    meals_chf: float | None = None
    if req.include_meals:
        meals_chf = meals_engine.calculate_meals_cantonal(req.meal_situation, req.work_schedule, rules)

    other_chf: float | None = None
    if req.include_other_expenses and req.annual_net_salary_chf is not None:
        other_chf = other_expenses.calculate_other_cantonal(req.annual_net_salary_chf, rules)

    total = transport.net_deduction_chf + (meals_chf or 0.0) + (other_chf or 0.0)

    # Confronto con forfait globale (se disponibile per l'anno)
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


def _build_federal(req: DeductionRequest, one_way_km: float | None, rules: FiscalYearRules) -> TaxLevelResult:
    transport = federal_engine.calculate_transport(
        transport_mode=req.transport_mode,
        one_way_km=one_way_km,
        work_schedule=req.work_schedule,
        rules=rules,
        annual_public_transport_cost_chf=req.annual_public_transport_cost_chf,
        car_distance_km_mixed=req.car_distance_km_mixed,
        public_transport_cost_mixed_chf=req.public_transport_cost_mixed_chf,
    )

    meals_chf: float | None = None
    if req.include_meals:
        meals_chf = meals_engine.calculate_meals_federal(req.meal_situation, req.work_schedule, rules)

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
