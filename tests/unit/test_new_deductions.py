"""
Test per le 3 nuove deduzioni aggiunte da Tabella_deduzioni_PF_2025.pdf:
  - lavori a turni (shift_work)
  - alloggio residente settimanale (annual_accommodation_cost_chf)
  - attività accessoria dipendente (include_secondary_activity)
"""
from __future__ import annotations
import pytest
from app.core import meals_engine, other_expenses
from app.rules.loader import load_rules
from app.schemas.request import MealSituation, WorkSchedule


SCHEDULE_5_0 = WorkSchedule(days_per_week=5, home_office_days_per_week=0)


# ─── SHIFT WORK ──────────────────────────────────────────────────────────────

class TestShiftWork:
    def test_cantonal_max_3200(self):
        rules = load_rules(2025)
        # 15 CHF/giorno × 220 giorni = 3'300 → cappato a 3'200
        result, _ = meals_engine.calculate_meals_cantonal(MealSituation.SHIFT_WORK, SCHEDULE_5_0, rules)
        assert result == 3200.0

    def test_federal_max_3200(self):
        rules = load_rules(2025)
        result, _ = meals_engine.calculate_meals_federal(MealSituation.SHIFT_WORK, SCHEDULE_5_0, rules)
        assert result == 3200.0

    def test_partial_days_no_cap(self):
        # 2 giorni/settimana × 44 settimane = 88 giorni × 15 = 1'320 → sotto il cap
        rules = load_rules(2025)
        schedule = WorkSchedule(days_per_week=2, home_office_days_per_week=0)
        result, _ = meals_engine.calculate_meals_cantonal(MealSituation.SHIFT_WORK, schedule, rules)
        assert result == 1320.0

    def test_same_rate_as_without_cafeteria(self):
        # I lavori a turni usano la stessa tariffa CHF 15/giorno di without_cafeteria
        rules = load_rules(2025)
        assert rules.cantonal_TI.meals.shift_work is not None
        assert rules.cantonal_TI.meals.shift_work.rate_chf_per_day == 15.0

    def test_2026_also_configured(self):
        rules = load_rules(2026)
        assert rules.cantonal_TI.meals.shift_work is not None
        assert rules.federal_IFD.meals.shift_work is not None


# ─── ALLOGGIO RESIDENTE SETTIMANALE ──────────────────────────────────────────

class TestWeeklyResidentAccommodation:
    def test_accommodation_rule_loaded(self):
        rules = load_rules(2025)
        acc = rules.cantonal_TI.meals.weekly_resident_accommodation
        assert acc is not None
        assert acc.mode == "actual_cost"
        assert acc.cap_chf is None

    def test_accommodation_rule_federal(self):
        rules = load_rules(2025)
        acc = rules.federal_IFD.meals.weekly_resident_accommodation
        assert acc is not None
        assert acc.mode == "actual_cost"

    def test_2026_configured(self):
        rules = load_rules(2026)
        assert rules.cantonal_TI.meals.weekly_resident_accommodation is not None


# ─── ATTIVITÀ ACCESSORIA DIPENDENTE ──────────────────────────────────────────

class TestSecondaryActivity:
    def test_cantonal_flat_rate_800(self):
        rules = load_rules(2025)
        result = other_expenses.calculate_secondary_cantonal(rules)
        assert result == 800.0

    def test_federal_20pct_salary(self):
        # 20% × 10'000 = 2'000 → ma min è 800 → 2'000 (sopra il min, sotto il max 2'400)
        rules = load_rules(2025)
        result = other_expenses.calculate_secondary_federal(10_000.0, rules)
        assert result == 2000.0

    def test_federal_minimum_800(self):
        # 20% × 3'000 = 600 → min 800 → 800
        rules = load_rules(2025)
        result = other_expenses.calculate_secondary_federal(3_000.0, rules)
        assert result == 800.0

    def test_federal_maximum_2400(self):
        # 20% × 20'000 = 4'000 → max 2'400 → 2'400
        rules = load_rules(2025)
        result = other_expenses.calculate_secondary_federal(20_000.0, rules)
        assert result == 2400.0

    def test_federal_no_salary_returns_zero(self):
        rules = load_rules(2025)
        result = other_expenses.calculate_secondary_federal(None, rules)
        assert result == 0.0

    def test_cantonal_2026(self):
        rules = load_rules(2026)
        result = other_expenses.calculate_secondary_cantonal(rules)
        assert result == 800.0

    def test_federal_2026(self):
        rules = load_rules(2026)
        result = other_expenses.calculate_secondary_federal(10_000.0, rules)
        assert result == 2000.0
