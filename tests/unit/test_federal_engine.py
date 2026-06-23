"""Test unitari per federal_engine — verifica soprattutto il cap CHF 3'300."""
import pytest
from app.core import federal_engine
from app.rules.loader import load_rules
from app.schemas.request import TransportMode, WorkSchedule


@pytest.fixture
def rules_2026():
    return load_rules(2026)


@pytest.fixture
def schedule_full():
    return WorkSchedule(days_per_week=5.0, home_office_days_per_week=0.0)


class TestFederalPrivateCar:
    def test_under_cap(self, rules_2026, schedule_full):
        # 5km × 0.75 × 2 × 220 = 1650 < 3300: non cappato
        result = federal_engine.calculate_transport(
            TransportMode.PRIVATE_CAR, 5.0, schedule_full, rules_2026,
        )
        assert result.net_deduction_chf == pytest.approx(1650.0, rel=0.01)
        assert not result.lines[0].capped

    def test_over_cap_is_capped(self, rules_2026, schedule_full):
        # 20km × 0.75 × 2 × 220 = 6600 > 3300: deve essere cappato a 3300
        result = federal_engine.calculate_transport(
            TransportMode.PRIVATE_CAR, 20.0, schedule_full, rules_2026,
        )
        cap = rules_2026.federal_IFD.transport.private_car.cap_chf
        assert result.net_deduction_chf == cap
        assert result.lines[0].capped

    def test_exact_cap(self, rules_2026, schedule_full):
        # 10km × 0.75 × 2 × 220 = 3300: esattamente al cap
        result = federal_engine.calculate_transport(
            TransportMode.PRIVATE_CAR, 10.0, schedule_full, rules_2026,
        )
        assert result.net_deduction_chf == pytest.approx(3300.0, rel=0.01)


class TestFederalPublicTransport:
    def test_no_cap_on_public_transport(self, rules_2026, schedule_full):
        # I mezzi pubblici non hanno cap nemmeno a livello IFD
        result = federal_engine.calculate_transport(
            TransportMode.PUBLIC_TRANSPORT, None, schedule_full, rules_2026,
            annual_public_transport_cost_chf=5000.0,
        )
        assert result.net_deduction_chf == 5000.0
        assert not result.lines[0].capped


class TestFederalBicycle:
    def test_flat_rate(self, rules_2026, schedule_full):
        result = federal_engine.calculate_transport(
            TransportMode.BICYCLE, None, schedule_full, rules_2026,
        )
        assert result.net_deduction_chf == 700.0
        assert result.gross_deduction_chf == 700.0
        assert result.lines[0].label == "Bicicletta / e-bike"
