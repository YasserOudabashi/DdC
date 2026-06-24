from __future__ import annotations
import yaml
from pathlib import Path
from functools import lru_cache
from .models import FiscalYearRules

_RULES_DIR = Path(__file__).parent.parent.parent / "rules"


@lru_cache(maxsize=10)
def load_rules(fiscal_year: int) -> FiscalYearRules:
    path = _RULES_DIR / f"{fiscal_year}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"Anno fiscale {fiscal_year} non supportato."
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return FiscalYearRules.model_validate(raw)
