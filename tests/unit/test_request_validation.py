"""Test unitari per i validator cross-field di DeductionRequest."""
import pytest
from pydantic import ValidationError
from app.schemas.request import DeductionRequest, TransportMode


def _base_request(**kwargs) -> dict:
    base = {
        "fiscal_year": 2026,
        "home_address": {"city": "Lugano", "postal_code": "6900"},
        "work_address": {"city": "Bellinzona", "postal_code": "6500"},
        "transport_mode": "public_transport",
        "annual_public_transport_cost_chf": 1200.0,
    }
    base.update(kwargs)
    return base


class TestOtherExpensesValidation:
    def test_other_expenses_without_salary_raises_422(self):
        with pytest.raises(ValidationError) as exc_info:
            DeductionRequest(**_base_request(include_other_expenses=True))
        errors = exc_info.value.errors()
        assert any(
            "annual_net_salary_chf" in str(e["msg"]) for e in errors
        )

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
