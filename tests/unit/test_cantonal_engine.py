"""
Test unitari per cantonal_engine.
Nessun I/O, nessuna rete — solo logica pura.
"""
import pytest
from app.core import cantonal_engine
from app.rules.loader import load_rules
from app.schemas.request import TransportMode, WorkSchedule


@pytest.fixture
def rules_2026():
    return load_rules(2026)


@pytest.fixture
def schedule_full():
    return WorkSchedule(days_per_week=5.0, home_office_days_per_week=0.0)


@pytest.fixture
def schedule_2d_home_office():
    return WorkSchedule(days_per_week=5.0, home_office_days_per_week=2.0)


class TestPublicTransport:
    def test_with_known_cost(self, rules_2026, schedule_full):
        result = cantonal_engine.calculate_transport(
            TransportMode.PUBLIC_TRANSPORT, None, schedule_full, rules_2026,
            annual_public_transport_cost_chf=1200.0,
        )
        assert result.net_deduction_chf == 1200.0
        assert result.effective_working_days == 220

    def test_no_cap_cantonal(self, rules_2026, schedule_full):
        # Cantonale: nessun tetto per i mezzi pubblici
        result = cantonal_engine.calculate_transport(
            TransportMode.PUBLIC_TRANSPORT, None, schedule_full, rules_2026,
            annual_public_transport_cost_chf=9999.0,
        )
        assert result.net_deduction_chf == 9999.0
        assert not result.lines[0].capped

    def test_home_office_reduces_days(self, rules_2026, schedule_2d_home_office):
        # Con 2 giorni home office su 5 → 3/5 dei giorni standard
        result = cantonal_engine.calculate_transport(
            TransportMode.PUBLIC_TRANSPORT, None, schedule_2d_home_office, rules_2026,
            annual_public_transport_cost_chf=1200.0,
        )
        # I giorni effettivi = 220 * (3/5) = 132
        assert result.effective_working_days == 132


class TestPrivateCar:
    def test_basic_calculation(self, rules_2026, schedule_full):
        # 10km × 0.75 × 2 × 220 = 3300.0
        result = cantonal_engine.calculate_transport(
            TransportMode.PRIVATE_CAR, 10.0, schedule_full, rules_2026,
        )
        expected = 0.75 * 10.0 * 2 * 220
        assert result.gross_deduction_chf == pytest.approx(expected, rel=0.01)

    def test_no_cap_cantonal(self, rules_2026, schedule_full):
        # Cantonale: nessun tetto su auto privata (a differenza dell'IFD)
        result = cantonal_engine.calculate_transport(
            TransportMode.PRIVATE_CAR, 50.0, schedule_full, rules_2026,
        )
        assert not result.lines[0].capped

    def test_requires_distance(self, rules_2026, schedule_full):
        with pytest.raises(ValueError):
            cantonal_engine.calculate_transport(
                TransportMode.PRIVATE_CAR, None, schedule_full, rules_2026,
            )


class TestBicycle:
    def test_flat_rate(self, rules_2026, schedule_full):
        result = cantonal_engine.calculate_transport(
            TransportMode.BICYCLE, None, schedule_full, rules_2026,
        )
        assert result.net_deduction_chf == 700.0
        assert result.gross_deduction_chf == 700.0
