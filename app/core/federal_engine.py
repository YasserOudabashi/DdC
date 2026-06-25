"""
Motore di calcolo federale — Art. 26 LIFD.
Cap CHF 3'300/anno su veicoli privati (RS 642.118.1).
"""
from __future__ import annotations
from ..rules.models import FiscalYearRules, TaxLevelRules, MotorcycleRule
from ..schemas.request import TransportMode, WorkSchedule
from ..schemas.response import TransportResult, DeductionLine


def _ho_suffix(work_schedule: WorkSchedule | None, standard_annual: int) -> str:
    if work_schedule is None or work_schedule.home_office_days_per_week <= 0:
        return ""
    office_days = work_schedule.days_per_week - work_schedule.home_office_days_per_week
    return f" ({standard_annual}/5 sett. × {office_days:.0f} gg/sett. in ufficio)"


def calculate_transport(
    transport_mode: TransportMode,
    one_way_km: float | None,
    work_schedule: WorkSchedule | None,
    rules: FiscalYearRules,
    annual_public_transport_cost_chf: float | None = None,
    car_distance_km_mixed: float | None = None,
    public_transport_cost_mixed_chf: float | None = None,
) -> TransportResult:
    r: TaxLevelRules = rules.federal_IFD
    standard_annual = rules.working_days.standard_annual
    if work_schedule is None:
        work_schedule = WorkSchedule()
    weeks = standard_annual / 5.0
    office_days = work_schedule.days_per_week - work_schedule.home_office_days_per_week
    effective_days = max(0, round(weeks * office_days))

    if transport_mode == TransportMode.PUBLIC_TRANSPORT:
        return _public_transport_federal(r, effective_days, annual_public_transport_cost_chf, one_way_km)

    if transport_mode == TransportMode.PRIVATE_CAR:
        return _private_car_federal(r, effective_days, one_way_km, rules, work_schedule, standard_annual)

    if transport_mode == TransportMode.BICYCLE:
        amount = r.transport.bicycle.flat_rate_chf_per_year
        return TransportResult(
            mode="bicycle",
            one_way_distance_km=None,
            effective_working_days=effective_days,
            gross_deduction_chf=amount,
            net_deduction_chf=amount,
            lines=[DeductionLine(
                label="Bicicletta / e-bike",
                amount_chf=amount,
                basis=f"Forfait annuale CHF {amount:.0f}",
                legal_reference="Art. 26 LIFD",
            )],
        )

    if transport_mode == TransportMode.MIXED:
        return _mixed_federal(r, effective_days, car_distance_km_mixed, public_transport_cost_mixed_chf, rules, work_schedule, standard_annual)

    if transport_mode == TransportMode.MOTORCYCLE:
        return _motorcycle_federal(r, effective_days, one_way_km, rules, work_schedule, standard_annual)

    raise ValueError(f"TransportMode non supportato: {transport_mode}")


def _public_transport_federal(
    r: TaxLevelRules, effective_days: int,
    annual_cost: float | None, one_way_km: float | None,
) -> TransportResult:
    if annual_cost is not None:
        gross = annual_cost
        basis = f"Costo effettivo abbonamento annuale CHF {annual_cost:.2f}"
    elif one_way_km is not None:
        gross = one_way_km * 0.065 * effective_days * 2
        basis = f"Stima: {one_way_km:.1f}km × CHF 0.065/km × 2 × {effective_days} giorni"
    else:
        gross = 0.0
        basis = "Nessun costo fornito"

    cap = r.transport.public_transport.cap_chf
    net = min(gross, cap) if cap else gross
    return TransportResult(
        mode="public_transport",
        one_way_distance_km=one_way_km,
        effective_working_days=effective_days,
        gross_deduction_chf=round(gross, 2),
        net_deduction_chf=round(net, 2),
        lines=[DeductionLine(
            label="Mezzi pubblici (IFD)",
            amount_chf=round(net, 2),
            basis=basis,
            legal_reference="Art. 26 LIFD",
            capped=False,
        )],
    )


def _private_car_federal(
    r: TaxLevelRules, effective_days: int,
    one_way_km: float | None, rules: FiscalYearRules,
    work_schedule: WorkSchedule | None = None, standard_annual: int = 220,
) -> TransportResult:
    if one_way_km is None:
        raise ValueError("one_way_km obbligatorio per PRIVATE_CAR")

    federal_rate = r.transport.private_car.rate_chf_per_km
    if federal_rate is None:
        raise ValueError("rate_chf_per_km IFD non trovato nel YAML — aggiornare rules/<anno>.yaml")

    gross = federal_rate * one_way_km * 2 * effective_days
    cap = r.transport.private_car.cap_chf
    net = min(gross, cap) if cap else gross
    basis = f"CHF {federal_rate}/km × {one_way_km:.1f}km × 2 × {effective_days} giorni → cap CHF {cap:.0f}"
    basis += _ho_suffix(work_schedule, standard_annual)

    return TransportResult(
        mode="private_car",
        one_way_distance_km=one_way_km,
        effective_working_days=effective_days,
        gross_deduction_chf=round(gross, 2),
        net_deduction_chf=round(net, 2),
        lines=[DeductionLine(
            label="Auto privata (IFD — soggetta a tetto massimo)",
            amount_chf=round(net, 2),
            basis=basis,
            legal_reference="Art. 26 LIFD + RS 642.118.1",
            capped=cap is not None and gross > cap,
            cap_amount_chf=cap,
        )],
    )


def _motorcycle_federal(
    r: TaxLevelRules, effective_days: int,
    one_way_km: float | None, rules: FiscalYearRules,
    work_schedule: WorkSchedule | None = None, standard_annual: int = 220,
) -> TransportResult:
    if one_way_km is None:
        raise ValueError("one_way_km obbligatorio per TransportMode.MOTORCYCLE")

    moto: MotorcycleRule | None = r.transport.motorcycle_white_plate
    if moto is None:
        raise ValueError("motorcycle_white_plate non trovato nelle regole IFD dell'anno selezionato")

    rate = moto.rate_chf_per_km
    gross = rate * one_way_km * 2 * effective_days
    cap = r.transport.private_car.cap_chf
    net = min(gross, cap) if cap else gross
    basis = f"CHF {rate}/km × {one_way_km:.1f}km × 2 × {effective_days} giorni → cap CHF {cap:.0f}"
    basis += _ho_suffix(work_schedule, standard_annual)

    return TransportResult(
        mode="motorcycle",
        one_way_distance_km=one_way_km,
        effective_working_days=effective_days,
        gross_deduction_chf=round(gross, 2),
        net_deduction_chf=round(net, 2),
        lines=[DeductionLine(
            label="Motocicletta targa bianca (IFD — soggetta a tetto massimo)",
            amount_chf=round(net, 2),
            basis=basis,
            legal_reference="Art. 26 LIFD + RS 642.118.1 Appendice",
            capped=cap is not None and gross > cap,
            cap_amount_chf=cap,
        )],
    )


def _mixed_federal(
    r: TaxLevelRules, effective_days: int,
    car_km: float | None, pt_cost: float | None,
    rules: FiscalYearRules,
    work_schedule: WorkSchedule | None = None, standard_annual: int = 220,
) -> TransportResult:
    lines: list[DeductionLine] = []
    total = 0.0

    if car_km is not None:
        rate = r.transport.private_car.rate_chf_per_km or 0.0
        car_gross = rate * car_km * 2 * effective_days
        cap = r.transport.private_car.cap_chf
        car_net = min(car_gross, cap) if cap else car_gross
        total += car_net
        basis = f"CHF {rate}/km × {car_km:.1f}km × 2 × {effective_days} giorni → max CHF {cap:.0f}"
        basis += _ho_suffix(work_schedule, standard_annual)
        lines.append(DeductionLine(
            label="Auto (tratto park & ride) — IFD",
            amount_chf=round(car_net, 2),
            basis=basis,
            legal_reference="Art. 26 LIFD + RS 642.118.1",
            capped=cap is not None and car_gross > cap,
            cap_amount_chf=cap,
        ))

    if pt_cost is not None:
        total += pt_cost
        lines.append(DeductionLine(
            label="Mezzi pubblici (tratto rimanente) — IFD",
            amount_chf=round(pt_cost, 2),
            basis=f"Costo effettivo CHF {pt_cost:.2f}",
            legal_reference="Art. 26 LIFD",
        ))

    return TransportResult(
        mode="mixed",
        effective_working_days=effective_days,
        gross_deduction_chf=round(total, 2),
        net_deduction_chf=round(total, 2),
        lines=lines,
    )
