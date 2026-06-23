"""Altre spese professionali — Art. 25 cpv. 1 lett. c LT / Art. 26 cpv. 1 lett. c LIFD."""
from __future__ import annotations
from ..rules.models import FiscalYearRules, OtherExpensesRule


def calculate_other_cantonal(annual_net_salary_chf: float, rules: FiscalYearRules) -> float:
    rule = rules.cantonal_TI.other_expenses
    return _calculate(annual_net_salary_chf, rule)


def calculate_other_federal(annual_net_salary_chf: float, rules: FiscalYearRules) -> float:
    rule = rules.federal_IFD.other_expenses
    return _calculate(annual_net_salary_chf, rule)


def _calculate(salary: float, rule: OtherExpensesRule) -> float:
    if rule.method == "flat_rate":
        # Cantonale TI: forfait fisso (CHF 3'000 per 2025, da Decreto CdS per anno successivo)
        return round(rule.flat_rate_chf or 0.0, 2)
    # Federal IFD: 3% salario netto, min CHF 2'000, max CHF 4'000
    raw = (salary * (rule.rate_percent or 0.0) / 100.0)
    return round(max(rule.minimum_chf or 0.0, min(raw, rule.maximum_chf or float("inf"))), 2)
