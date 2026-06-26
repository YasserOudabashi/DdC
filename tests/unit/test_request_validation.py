"""Test unitari per i validator cross-field di DeductionRequest."""
import pytest
from pydantic import ValidationError
from app.schemas.request import DeductionRequest, TransportMode


def _base_request(**kwargs) -> dict:
    base = {
        "fiscal_year": 2026,
        "home_address": {"street": "Via Nassa 10", "city": "Lugano", "postal_code": "6900"},
        "work_address": {"street": "Viale Franscini 30", "city": "Bellinzona", "postal_code": "6500"},
        "transport_mode": "public_transport",
        "annual_public_transport_cost_chf": 1200.0,
    }
    base.update(kwargs)
    return base


class TestOtherExpensesValidation:
    def test_other_expenses_without_salary_accepted(self):
        # IC uses flat-rate CHF 3'000 (salary not needed); IFD skips altri spese if salary absent
        req = DeductionRequest(**_base_request(include_other_expenses=True))
        assert req.include_other_expenses is True
        assert req.annual_net_salary_chf is None

    def test_other_expenses_with_salary_accepted(self):
        req = DeductionRequest(**_base_request(
            include_other_expenses=True,
            annual_net_salary_chf=80000.0,
        ))
        assert req.include_other_expenses is True
        assert req.annual_net_salary_chf == 80000.0

    def test_no_other_expenses_salary_optional(self):
        req = DeductionRequest(**_base_request(include_other_expenses=False))
        assert req.annual_net_salary_chf is None


class TestMixedTransportValidation:
    def test_mixed_without_any_data_raises_422(self):
        with pytest.raises(ValidationError) as exc_info:
            DeductionRequest(**_base_request(transport_mode="mixed"))
        errors = exc_info.value.errors()
        assert any(
            "mixed" in str(e["msg"]) for e in errors
        )

    def test_mixed_with_car_distance_accepted(self):
        req = DeductionRequest(**_base_request(
            transport_mode="mixed",
            car_distance_km_mixed=5.0,
        ))
        assert req.car_distance_km_mixed == 5.0

    def test_mixed_with_public_transport_cost_accepted(self):
        req = DeductionRequest(**_base_request(
            transport_mode="mixed",
            public_transport_cost_mixed_chf=1200.0,
        ))
        assert req.public_transport_cost_mixed_chf == 1200.0

    def test_mixed_with_both_fields_accepted(self):
        req = DeductionRequest(**_base_request(
            transport_mode="mixed",
            car_distance_km_mixed=5.0,
            public_transport_cost_mixed_chf=1200.0,
        ))
        assert req.car_distance_km_mixed == 5.0
        assert req.public_transport_cost_mixed_chf == 1200.0

    def test_non_mixed_mode_ignores_mixed_fields(self):
        req = DeductionRequest(**_base_request(transport_mode="public_transport"))
        assert req.car_distance_km_mixed is None
        assert req.public_transport_cost_mixed_chf is None


class TestNumericLimits:
    def test_override_distance_km_max(self):
        with pytest.raises(ValidationError):
            DeductionRequest(**_base_request(
                transport_mode="private_car",
                override_distance_km=501.0,
            ))

    def test_annual_pt_cost_max(self):
        with pytest.raises(ValidationError):
            DeductionRequest(**_base_request(annual_public_transport_cost_chf=20001.0))

    def test_annual_pt_cost_at_limit_accepted(self):
        req = DeductionRequest(**_base_request(annual_public_transport_cost_chf=20000.0))
        assert req.annual_public_transport_cost_chf == 20000.0

    def test_salary_max(self):
        with pytest.raises(ValidationError):
            DeductionRequest(**_base_request(
                include_other_expenses=True,
                annual_net_salary_chf=1_000_001.0,
            ))

    def test_company_car_max(self):
        with pytest.raises(ValidationError):
            DeductionRequest(**_base_request(
                transport_mode="private_car",
                company_car_monthly_chf=2001.0,
            ))

    def test_accommodation_monthly_max(self):
        with pytest.raises(ValidationError):
            DeductionRequest(**_base_request(
                residency_type="weekly_resident",
                accommodation_monthly_chf=5001.0,
            ))


class TestCrossFieldValidation:
    def test_arcobaleno_and_manual_cost_conflict(self):
        with pytest.raises(ValidationError, match="incompatibili"):
            DeductionRequest(**_base_request(
                arcobaleno_zones=3,
                annual_public_transport_cost_chf=1200.0,
            ))

    def test_arcobaleno_without_manual_cost_accepted(self):
        req = DeductionRequest(**_base_request(
            arcobaleno_zones=3,
            annual_public_transport_cost_chf=None,
        ))
        assert req.arcobaleno_zones == 3

    def test_accommodation_both_fields_conflict(self):
        with pytest.raises(ValidationError, match="non entrambi"):
            DeductionRequest(**_base_request(
                residency_type="weekly_resident",
                annual_accommodation_cost_chf=7800.0,
                accommodation_monthly_chf=650.0,
            ))

    def test_company_car_requires_private_car(self):
        with pytest.raises(ValidationError, match="private_car"):
            DeductionRequest(**_base_request(
                transport_mode="public_transport",
                company_car_monthly_chf=500.0,
                annual_public_transport_cost_chf=1200.0,
            ))

    def test_home_office_exceeds_days_raises(self):
        with pytest.raises(ValidationError):
            DeductionRequest(**_base_request(
                work_schedule={"days_per_week": 3.0, "home_office_days_per_week": 4.0},
            ))
