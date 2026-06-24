from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class TransportMode(str, Enum):
    PUBLIC_TRANSPORT = "public_transport"
    PRIVATE_CAR      = "private_car"
    BICYCLE          = "bicycle"
    MIXED            = "mixed"
    MOTORCYCLE       = "motorcycle"


class ResidencyType(str, Enum):
    RESIDENT_TI     = "resident_TI"
    FRONTALIERE     = "frontaliere"
    WEEKLY_RESIDENT = "weekly_resident"


class MealSituation(str, Enum):
    HOME                         = "home"                          # nessuna deduzione
    WITHOUT_CAFETERIA            = "without_cafeteria"             # Art. 6 cpv. 1: CHF 15/giorno
    WITH_CAFETERIA               = "with_cafeteria"                # Art. 6 cpv. 2: CHF 7.50/giorno (mezza)
    SHIFT_WORK                   = "shift_work"                    # lavori a turni: CHF 15/giorno, max 3'200
    WEEKLY_RESIDENT              = "weekly_resident"               # Art. 9: CHF 30/giorno
    WEEKLY_RESIDENT_WITH_CAFETERIA = "weekly_resident_with_cafeteria"  # Art. 9+6: CHF 22.50/giorno


class Address(BaseModel):
    street: Optional[str] = None
    city: str
    postal_code: str
    country: str = "CH"

    def full_address(self) -> str:
        parts = []
        if self.street:
            parts.append(self.street)
        parts.append(f"{self.postal_code} {self.city}")
        if self.country != "CH":
            parts.append(self.country)
        return ", ".join(parts)


class WorkSchedule(BaseModel):
    days_per_week: float = Field(default=5.0, ge=0.5, le=7.0)
    home_office_days_per_week: float = Field(default=0.0, ge=0.0, le=7.0)

    @model_validator(mode="after")
    def validate_home_office(self) -> WorkSchedule:
        if self.home_office_days_per_week > self.days_per_week:
            raise ValueError("home_office_days_per_week non può superare days_per_week")
        return self


class DeductionRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "fiscal_year": 2026,
        "home_address": {"street": "Via Nassa 10", "city": "Lugano", "postal_code": "6900"},
        "work_address": {"street": "Viale Franscini 30", "city": "Bellinzona", "postal_code": "6500"},
        "transport_mode": "public_transport",
        "residency_type": "resident_TI",
        "work_schedule": {"days_per_week": 5.0, "home_office_days_per_week": 0.0},
        "meal_situation": "without_cafeteria",
        "annual_public_transport_cost_chf": 1800.0,
        "include_meals": True,
        "include_other_expenses": False,
    }})

    fiscal_year: int = Field(default=2026, ge=2020, le=2030)
    home_address: Address
    work_address: Address
    transport_mode: TransportMode
    residency_type: ResidencyType = ResidencyType.RESIDENT_TI
    work_schedule: WorkSchedule = Field(default_factory=WorkSchedule)
    meal_situation: MealSituation = MealSituation.HOME

    override_distance_km: Optional[float] = Field(default=None, ge=0.1, le=500.0)
    car_distance_km_mixed: Optional[float] = Field(default=None, ge=0.0)
    public_transport_cost_mixed_chf: Optional[float] = Field(default=None, ge=0.0)
    annual_public_transport_cost_chf: Optional[float] = Field(default=None, ge=0.0)
    annual_net_salary_chf: Optional[float] = Field(default=None, ge=0.0)

    employer_pays_transport: bool = Field(default=False)
    employer_has_cafeteria: bool = Field(default=False)
    company_car_monthly_chf: Optional[float] = Field(default=None, ge=0.0)

    annual_accommodation_cost_chf: Optional[float] = Field(default=None, ge=0.0)

    include_meals: bool = Field(default=False)
    include_other_expenses: bool = Field(default=False)
    include_secondary_activity: bool = Field(default=False)

    @model_validator(mode="after")
    def validate_other_expenses_requires_salary(self) -> DeductionRequest:
        if self.include_other_expenses and self.annual_net_salary_chf is None:
            raise ValueError(
                "annual_net_salary_chf è obbligatorio quando include_other_expenses è true"
            )
        return self

    @model_validator(mode="after")
    def validate_mixed_transport_requires_data(self) -> DeductionRequest:
        if (
            self.transport_mode == TransportMode.MIXED
            and self.car_distance_km_mixed is None
            and self.public_transport_cost_mixed_chf is None
        ):
            raise ValueError(
                "Per transport_mode mixed è necessario fornire almeno car_distance_km_mixed o public_transport_cost_mixed_chf"
            )
        return self
