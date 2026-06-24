"""
Calcolo deduzioni pasti fuori domicilio.
Art. 6 RS 642.118.1 + Art. 9 (soggiorno fuori domicilio per residenti settimanali).
"""
from __future__ import annotations
from ..rules.models import FiscalYearRules, MealsRules
from ..schemas.request import MealSituation, WorkSchedule


def calculate_meals_cantonal(
    meal_situation: MealSituation,
    work_schedule: WorkSchedule,
    rules: FiscalYearRules,
) -> float:
    return _calculate(meal_situation, work_schedule, rules.cantonal_TI.meals,
                      rules.working_days.standard_annual)


def calculate_meals_federal(
    meal_situation: MealSituation,
    work_schedule: WorkSchedule,
    rules: FiscalYearRules,
) -> float:
    return _calculate(meal_situation, work_schedule, rules.federal_IFD.meals,
                      rules.working_days.standard_annual)


def _calculate(
    meal_situation: MealSituation,
    work_schedule: WorkSchedule,
    meals: MealsRules,
    standard_annual: int,
) -> float:
    if meal_situation == MealSituation.HOME:
        return 0.0

    weeks = standard_annual / 5.0
    office_days = work_schedule.days_per_week - work_schedule.home_office_days_per_week
    effective_days = max(0, round(weeks * office_days))

    if meal_situation == MealSituation.SHIFT_WORK:
        if meals.shift_work is None:
            raise ValueError("shift_work non configurato nelle regole per questo anno fiscale")
        rule = meals.shift_work
        gross = rule.rate_chf_per_day * effective_days
        return round(min(gross, rule.annual_max_chf), 2)

    rule_map = {
        MealSituation.WITHOUT_CAFETERIA:             meals.without_cafeteria,
        MealSituation.WITH_CAFETERIA:                meals.with_cafeteria,
        MealSituation.WEEKLY_RESIDENT:               meals.weekly_resident,
        MealSituation.WEEKLY_RESIDENT_WITH_CAFETERIA: meals.weekly_resident_with_cafeteria,
    }
    rule = rule_map[meal_situation]
    gross = rule.rate_chf_per_day * effective_days
    return round(min(gross, rule.annual_max_chf), 2)
