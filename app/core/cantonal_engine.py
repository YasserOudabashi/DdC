"""
Motore di calcolo cantonale — Art. 25 LT Canton Ticino.
Funzioni pure: nessun I/O, nessun effetto collaterale.
Tutti i valori CHF vengono da FiscalYearRules (caricato dal YAML).
"""
from __future__ import annotations
from ..rules.models import FiscalYearRules, CantonalRules, MotorcycleRule
from ..schemas.request import TransportMode, WorkSchedule
from ..schemas.response import TransportResult, DeductionLine


def calculate_transport(
    transport_mode: TransportMode,
    one_way_km: float | None,
    work_schedule: WorkSchedule | None,
    rules: FiscalYearRules,
    annual_public_transport_cost_chf: float | None = None,
    car_distance_km_mixed: float | None = None,
    public_transport_cost_mixed_chf: float | None = None,
) -> TransportResult:
    r: CantonalRules = rules.cantonal_TI
    standard_annual = rules.working_days.standard_annual
    if work_schedule is None:
        work_schedule = WorkSchedule()
    effective_days = _effective_days(work_schedule, standard_annual)

    if transport_mode == TransportMode.PUBLIC_TRANSPORT:
        return _public_transport(r, effective_days, annual_public_transport_cost_chf, one_way_km)

    if transport_mode == TransportMode.PRIVATE_CAR:
        return _private_car(r, effective_days, one_way_km, work_schedule, standard_annual)

    if transport_mode == TransportMode.BICYCLE:
        return _bicycle(r, effective_days)

    if transport_mode == TransportMode.MIXED:
        return _mixed(r, effective_days, car_distance_km_mixed, public_transport_cost_mixed_chf, work_schedule, standard_annual)

    if transport_mode == TransportMode.MOTORCYCLE:
        return _motorcycle(r, effective_days, one_way_km, rules, work_schedule, standard_annual)

    raise ValueError(f"TransportMode non supportato: {transport_mode}")


# ─── Implementazioni ──────────────────────────────────────────────────────────

def _ho_suffix(work_schedule: WorkSchedule | None, standard_annual: int) -> str:
    if work_schedule is None or work_schedule.home_office_days_per_week <= 0:
        return ""
    office_days = work_schedule.days_per_week - work_schedule.home_office_days_per_week
    return f" ({standard_annual}/5 sett. × {office_days:.0f} gg/sett. in ufficio)"


def _effective_days(schedule: WorkSchedule, standard_annual: int) -> int:
    weeks = standard_annual / 5.0
    office_days_per_week = schedule.days_per_week - schedule.home_office_days_per_week
    return max(0, round(weeks * office_days_per_week))


def _public_transport(
    r: CantonalRules, effective_days: int,
    annual_cost: float | None, one_way_km: float | None,
) -> TransportResult:
    if annual_cost is not None:
        gross = annual_cost
        basis = f"Costo effettivo abbonamento annuale CHF {annual_cost:.2f}"
    elif one_way_km is not None:
        # Stima di massima se il costo non è noto
        gross = one_way_km * 0.065 * effective_days * 2   # ~6.5 Rappen/km stimati
        basis = f"Stima: {one_way_km:.1f}km × CHF 0.065/km × 2 × {effective_days} giorni"
    else:
        gross = 0.0
        basis = "Nessun costo fornito — fornire annual_public_transport_cost_chf per un calcolo accurato"

    cap = r.transport.public_transport.cap_chf
    net = min(gross, cap) if cap else gross
    return TransportResult(
        mode="public_transport",
        one_way_distance_km=one_way_km,
        effective_working_days=effective_days,
        gross_deduction_chf=round(gross, 2),
        net_deduction_chf=round(net, 2),
        lines=[DeductionLine(
            label="Mezzi pubblici",
            amount_chf=round(net, 2),
            basis=basis,
            legal_reference="Art. 25 cpv. 1 lett. a LT",
            capped=cap is not None and gross > cap,
            cap_amount_chf=cap,
        )],
    )


def _private_car(
    r: CantonalRules, effective_days: int, one_way_km: float | None,
    work_schedule: WorkSchedule | None = None, standard_annual: int = 220,
) -> TransportResult:
    if one_way_km is None:
        raise ValueError("one_way_km obbligatorio per TransportMode.PRIVATE_CAR")

    rate = r.transport.private_car.rate_chf_per_km
    if rate is None:
        raise ValueError("rate_chf_per_km non trovato nelle regole dell'anno selezionato")

    gross = rate * one_way_km * 2 * effective_days
    cap = r.transport.private_car.cap_chf
    net = min(gross, cap) if cap else gross
    basis = f"CHF {rate}/km × {one_way_km:.1f}km × 2 × {effective_days} giorni"
    basis += _ho_suffix(work_schedule, standard_annual)

    return TransportResult(
        mode="private_car",
        one_way_distance_km=one_way_km,
        effective_working_days=effective_days,
        gross_deduction_chf=round(gross, 2),
        net_deduction_chf=round(net, 2),
        lines=[DeductionLine(
            label="Auto privata",
            amount_chf=round(net, 2),
            basis=basis,
            legal_reference="Art. 25 cpv. 1 lett. a LT",
            capped=cap is not None and gross > cap,
            cap_amount_chf=cap,
        )],
    )


def _bicycle(r: CantonalRules, effective_days: int) -> TransportResult:
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
            legal_reference="Art. 25 cpv. 1 lett. a LT (decreto CdS)",
        )],
    )


def _motorcycle(
    r: CantonalRules, effective_days: int,
    one_way_km: float | None, rules: FiscalYearRules,
    work_schedule: WorkSchedule | None = None, standard_annual: int = 220,
) -> TransportResult:
    if one_way_km is None:
        raise ValueError("one_way_km obbligatorio per TransportMode.MOTORCYCLE")

    cantonal_moto: MotorcycleRule | None = r.transport.motorcycle_white_plate
    federal_moto: MotorcycleRule | None = rules.federal_IFD.transport.motorcycle_white_plate
    moto = cantonal_moto or federal_moto
    if moto is None:
        raise ValueError("motorcycle_white_plate non trovato nelle regole dell'anno selezionato")

    rate = moto.rate_chf_per_km
    gross = rate * one_way_km * 2 * effective_days
    basis = f"CHF {rate}/km × {one_way_km:.1f}km × 2 × {effective_days} giorni"
    basis += _ho_suffix(work_schedule, standard_annual)

    return TransportResult(
        mode="motorcycle",
        one_way_distance_km=one_way_km,
        effective_working_days=effective_days,
        gross_deduction_chf=round(gross, 2),
        net_deduction_chf=round(gross, 2),
        lines=[DeductionLine(
            label="Motocicletta (targa bianca)",
            amount_chf=round(gross, 2),
            basis=basis,
            legal_reference="Art. 25 cpv. 1 lett. a LT + RS 642.118.1 Appendice",
            capped=False,
        )],
    )


def _mixed(
    r: CantonalRules, effective_days: int,
    car_km: float | None, pt_cost: float | None,
    work_schedule: WorkSchedule | None = None, standard_annual: int = 220,
) -> TransportResult:
    lines: list[DeductionLine] = []
    total = 0.0

    if car_km is not None and r.transport.private_car.rate_chf_per_km:
        rate = r.transport.private_car.rate_chf_per_km
        car_amount = rate * car_km * 2 * effective_days
        total += car_amount
        basis = f"CHF {rate}/km × {car_km:.1f}km × 2 × {effective_days} giorni"
        basis += _ho_suffix(work_schedule, standard_annual)
        lines.append(DeductionLine(
            label="Auto (tratto fino al parcheggio)",
            amount_chf=round(car_amount, 2),
            basis=basis,
            legal_reference="Art. 25 cpv. 1 lett. a LT",
        ))

    if pt_cost is not None:
        total += pt_cost
        lines.append(DeductionLine(
            label="Mezzi pubblici (tratto rimanente)",
            amount_chf=round(pt_cost, 2),
            basis=f"Costo effettivo abbonamento tratto CHF {pt_cost:.2f}",
            legal_reference="Art. 25 cpv. 1 lett. a LT",
        ))

    return TransportResult(
        mode="mixed",
        effective_working_days=effective_days,
        gross_deduction_chf=round(total, 2),
        net_deduction_chf=round(total, 2),
        lines=lines,
    )
