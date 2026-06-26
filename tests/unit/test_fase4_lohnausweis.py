"""
Test unitari per Fase 4 — Integrazione campi Lohnausweis nel request.
US-401: employer_pays_transport (campo D)
US-402: employer_has_cafeteria (campo F)
US-403: company_car_monthly_chf (cifra 13.2.2)
"""
import pytest
from app.core import calculator
from app.schemas.request import (
    Address, DeductionRequest, MealSituation, TransportMode, WorkSchedule,
)


# ─── Fixture ──────────────────────────────────────────────────────────────────

@pytest.fixture
def base_request():
    return {
        "fiscal_year": 2026,
        "home_address": {"street": "Via Nassa 10", "city": "Lugano", "postal_code": "6900"},
        "work_address": {"city": "Bellinzona", "postal_code": "6500"},
        "transport_mode": "private_car",
        "residency_type": "resident_TI",
        "work_schedule": {"days_per_week": 5.0, "home_office_days_per_week": 0.0},
        "meal_situation": "home",
    }


def make_request(**kwargs) -> DeductionRequest:
    base = {
        "fiscal_year": 2026,
        "home_address": Address(street="Via Nassa 10", city="Lugano", postal_code="6900"),
        "work_address": Address(city="Bellinzona", postal_code="6500"),
        "transport_mode": TransportMode.PRIVATE_CAR,
        "work_schedule": WorkSchedule(),
        "meal_situation": MealSituation.HOME,
    }
    base.update(kwargs)
    return DeductionRequest(**base)


# ─── US-401: employer_pays_transport ──────────────────────────────────────────

class TestEmployerPaysTransport:
    def test_net_is_zero(self):
        req = make_request(employer_pays_transport=True)
        cantonal, federal = _run_both(req, one_way_km=20.0)
        assert cantonal.net_deduction_chf == 0.0
        assert federal.net_deduction_chf == 0.0

    def test_gross_still_shown(self):
        """Il gross mostra il valore teorico anche se net è azzerato."""
        req = make_request(employer_pays_transport=True)
        cantonal, _ = _run_both(req, one_way_km=20.0)
        assert cantonal.gross_deduction_chf > 0.0

    def test_label_and_legal_reference(self):
        req = make_request(employer_pays_transport=True)
        cantonal, _ = _run_both(req, one_way_km=20.0)
        line = cantonal.lines[0]
        assert line.label == "Trasporto a carico del datore di lavoro"
        assert "Art. 26 cpv. 2 LIFD" in line.legal_reference

    def test_default_false_unchanged(self):
        """employer_pays_transport=False (default) → calcolo normale."""
        req_normal = make_request()
        req_campo_d = make_request(employer_pays_transport=False)
        c_normal, _ = _run_both(req_normal, one_way_km=20.0)
        c_campo_d, _ = _run_both(req_campo_d, one_way_km=20.0)
        assert c_normal.net_deduction_chf == c_campo_d.net_deduction_chf
        assert c_normal.net_deduction_chf > 0.0

    def test_company_car_overrides_campo_d(self):
        """Se company_car_monthly_chf è presente, campo D viene ignorato."""
        req = make_request(
            employer_pays_transport=True,
            company_car_monthly_chf=500.0,
        )
        cantonal, _ = _run_both(req, one_way_km=20.0)
        # Con auto aziendale il net non è zero
        assert cantonal.net_deduction_chf == 500.0 * 12


# ─── US-402: employer_has_cafeteria ───────────────────────────────────────────

class TestEmployerHasCafeteria:
    def test_without_cafeteria_overridden_to_with_cafeteria(self):
        """without_cafeteria → with_cafeteria (CHF 7.50/giorno)."""
        req_no_campo_f = make_request(
            meal_situation=MealSituation.WITHOUT_CAFETERIA,
            include_meals=True,
        )
        req_campo_f = make_request(
            meal_situation=MealSituation.WITHOUT_CAFETERIA,
            employer_has_cafeteria=True,
            include_meals=True,
        )
        # Con mensa la deduzione pasti deve essere inferiore (7.50 < 15.00/giorno)
        c_no_f = _meals_cantonal(req_no_campo_f)
        c_si_f = _meals_cantonal(req_campo_f)
        assert c_si_f < c_no_f

    def test_weekly_resident_overridden(self):
        """weekly_resident → weekly_resident_with_cafeteria."""
        req_no = make_request(meal_situation=MealSituation.WEEKLY_RESIDENT, include_meals=True)
        req_si = make_request(
            meal_situation=MealSituation.WEEKLY_RESIDENT,
            employer_has_cafeteria=True,
            include_meals=True,
        )
        assert _meals_cantonal(req_si) < _meals_cantonal(req_no)

    def test_already_with_cafeteria_unchanged(self):
        """Se meal_situation è già with_cafeteria, campo F non cambia nulla."""
        req_no = make_request(meal_situation=MealSituation.WITH_CAFETERIA, include_meals=True)
        req_si = make_request(
            meal_situation=MealSituation.WITH_CAFETERIA,
            employer_has_cafeteria=True,
            include_meals=True,
        )
        assert _meals_cantonal(req_si) == _meals_cantonal(req_no)

    def test_home_meal_situation_unchanged(self):
        """meal_situation=home → nessuna deduzione pasti in ogni caso."""
        req = make_request(
            meal_situation=MealSituation.HOME,
            employer_has_cafeteria=True,
            include_meals=True,
        )
        assert _meals_cantonal(req) == 0.0 or _meals_cantonal(req) is None


# ─── US-403: company_car_monthly_chf ──────────────────────────────────────────

class TestCompanyCar:
    def test_high_monthly_cantonal_no_cap(self):
        """CHF 800/mese → cantonal CHF 9'600 (nessun cap cantonale)."""
        req = make_request(company_car_monthly_chf=800.0)
        cantonal, _ = _run_both(req, one_way_km=None)
        assert cantonal.net_deduction_chf == 9_600.0
        assert cantonal.gross_deduction_chf == 9_600.0

    def test_high_monthly_federal_capped(self):
        """CHF 800/mese → gross CHF 9'600, ma federal capped a CHF 3'300."""
        req = make_request(company_car_monthly_chf=800.0)
        _, federal = _run_both(req, one_way_km=None)
        assert federal.gross_deduction_chf == 9_600.0
        assert federal.net_deduction_chf == 3_300.0
        assert federal.lines[0].capped is True

    def test_low_monthly_both_uncapped(self):
        """CHF 200/mese → CHF 2'400 < cap IFD → entrambi i livelli CHF 2'400."""
        req = make_request(company_car_monthly_chf=200.0)
        cantonal, federal = _run_both(req, one_way_km=None)
        assert cantonal.net_deduction_chf == 2_400.0
        assert federal.net_deduction_chf == 2_400.0
        assert federal.lines[0].capped is False

    def test_legal_reference_art5a(self):
        req = make_request(company_car_monthly_chf=500.0)
        cantonal, federal = _run_both(req, one_way_km=None)
        assert "Art. 5a RS 642.118.1" in cantonal.lines[0].legal_reference
        assert "Art. 5a RS 642.118.1" in federal.lines[0].legal_reference

    def test_ignored_when_not_private_car(self):
        """Se transport_mode non è private_car, company_car viene ignorato."""
        req = make_request(
            transport_mode=TransportMode.PUBLIC_TRANSPORT,
            company_car_monthly_chf=800.0,
            annual_public_transport_cost_chf=1200.0,
        )
        cantonal, _ = _run_both(req, one_way_km=None)
        # Il calcolo usa il costo del TP, non il forfait auto aziendale
        assert cantonal.net_deduction_chf == 1200.0


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _run_both(
    req: DeductionRequest, one_way_km: float | None,
) -> tuple:
    """Restituisce (cantonal_transport, federal_transport)."""
    from app.core.calculator import _cantonal_transport, _federal_transport
    from app.rules.loader import load_rules
    rules = load_rules(req.fiscal_year)
    c = _cantonal_transport(req, one_way_km, rules)
    f = _federal_transport(req, one_way_km, rules)
    return c, f


def _meals_cantonal(req: DeductionRequest) -> float | None:
    """Calcola solo la deduzione pasti cantonale passando per il resolve."""
    from app.core.calculator import _resolve_meal_situation
    from app.core import meals_engine
    from app.rules.loader import load_rules
    rules = load_rules(req.fiscal_year)
    warnings: list[str] = []
    effective = _resolve_meal_situation(req, warnings)
    if not req.include_meals:
        return None
    chf, _ = meals_engine.calculate_meals_cantonal(effective, req.work_schedule, rules)
    return chf
