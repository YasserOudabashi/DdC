"""Test unitari per other_expenses — verifica minimo, normale e massimo IFD, e flat rate cantonale."""
import pytest
from app.core.other_expenses import calculate_other_cantonal, calculate_other_federal
from app.rules.loader import load_rules


@pytest.fixture
def rules_2026():
    return load_rules(2026)


class TestFederalOtherExpenses:
    def test_below_minimum_uses_minimum(self, rules_2026):
        # CHF 50'000 × 3% = CHF 1'500 < minimo CHF 2'000 → risultato CHF 2'000
        result = calculate_other_federal(50000.0, rules_2026)
        assert result == 2000.0

    def test_normal_range(self, rules_2026):
        # CHF 100'000 × 3% = CHF 3'000 → risultato CHF 3'000
        result = calculate_other_federal(100000.0, rules_2026)
        assert result == 3000.0

    def test_above_maximum_uses_maximum(self, rules_2026):
        # CHF 200'000 × 3% = CHF 6'000 > massimo CHF 4'000 → risultato CHF 4'000
        result = calculate_other_federal(200000.0, rules_2026)
        assert result == 4000.0


class TestCantonalOtherExpenses:
    def test_flat_rate_2026(self, rules_2026):
        # Cantonale TI 2026: forfait fisso CHF 3'000 indipendente dal salario
        result = calculate_other_cantonal(100000.0, rules_2026)
        assert result == 3000.0
