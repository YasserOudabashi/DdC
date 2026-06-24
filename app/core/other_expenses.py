"""Altre spese professionali — Art. 25 cpv. 1 lett. c LT / Art. 26 cpv. 1 lett. c LIFD."""
from __future__ import annotations
from ..rules.models import FiscalYearRules, OtherExpensesRule, SecondaryActivityRule


def calculate_other_cantonal(annual_net_salary_chf: float, rules: FiscalYearRules) -> float:
    rule = rules.cantonal_TI.other_expenses
    return _calculate(annual_net_salary_chf, rule)


def calculate_other_federal(annual_net_salary_chf: float, rules: FiscalYearRules) -> float:
    rule = rules.federal_IFD.other_expenses
    return _calculate(annual_net_salary_chf, rule)


def calculate_secondary_cantonal(rules: FiscalYearRules) -> float:
    """Spese per attività accessoria dipendente (IC): forfait CHF 800 o effettive."""
    rule = rules.cantonal_TI.other_expenses.secondary_activity
    if rule is None:
        return 0.0
    return round(rule.flat_rate_chf or 0.0, 2)


def calculate_secondary_federal(annual_net_salary_chf: float | None, rules: FiscalYearRules) -> float:
    """Spese per attività accessoria dipendente (IFD): 20% salario netto, min 800, max 2'400."""
    rule = rules.federal_IFD.other_expenses.secondary_activity
    if rule is None or annual_net_salary_chf is None:
        return 0.0
    return _calculate_secondary(annual_net_salary_chf, rule)


def _calculate(salary: float, rule: OtherExpensesRule) -> float:
    if rule.method == "flat_rate":
        return round(rule.flat_rate_chf or 0.0, 2)
    raw = (salary * (rule.rate_percent or 0.0) / 100.0)
    return round(max(rule.minimum_chf or 0.0, min(raw, rule.maximum_chf or float("inf"))), 2)


def _calculate_secondary(salary: float, rule: SecondaryActivityRule) -> float:
    if rule.method == "flat_rate_or_actual":
        return round(rule.flat_rate_chf or 0.0, 2)
    raw = salary * (rule.rate_percent or 0.0) / 100.0
    return round(max(rule.minimum_chf or 0.0, min(raw, rule.maximum_chf or float("inf"))), 2)
