"""Test unitari per l'anno fiscale 2025 — tariffe auto IC 0.60/km, IFD 0.70/km."""
import pytest
from app.core import cantonal_engine, federal_engine
from app.rules.loader import load_rules
from app.schemas.request import TransportMode, WorkSchedule


@pytest.fixture
def rules_2025():
    return load_rules(2025)


@pytest.fixture
def schedule_full():
    return WorkSchedule(days_per_week=5.0, home_office_days_per_week=0.0)


class TestCantonal2025:
    def test_private_car_rate_and_no_cap(self, rules_2025, schedule_full):
        # 20km × 0.60 × 2 × 220 = 5280.0 — cantonale: nessun cap
        result = cantonal_engine.calculate_transport(
            TransportMode.PRIVATE_CAR, 20.0, schedule_full, rules_2025,
        )
        assert rules_2025.cantonal_TI.transport.private_car.rate_chf_per_km == pytest.approx(0.60)
        assert result.gross_deduction_chf == pytest.approx(5280.0, rel=0.01)
        assert result.net_deduction_chf == pytest.approx(5280.0, rel=0.01)
        assert not result.lines[0].capped

    def test_rules_version(self, rules_2025):
        assert rules_2025.version == "2025"


class TestFederal2025:
    def test_private_car_over_cap(self, rules_2025, schedule_full):
        # 20km × 0.70 × 2 × 220 = 6160.0 → cappato a CHF 3'300 (IFD)
        result = federal_engine.calculate_transport(
            TransportMode.PRIVATE_CAR, 20.0, schedule_full, rules_2025,
        )
        assert rules_2025.federal_IFD.transport.private_car.rate_chf_per_km == pytest.approx(0.70)
        assert result.gross_deduction_chf == pytest.approx(6160.0, rel=0.01)
        assert result.net_deduction_chf == pytest.approx(3300.0, rel=0.01)
        assert result.lines[0].capped
