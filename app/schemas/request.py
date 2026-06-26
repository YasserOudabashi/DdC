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
    HOME                                   = "home"
    WITHOUT_CAFETERIA                      = "without_cafeteria"
    WITH_CAFETERIA                         = "with_cafeteria"
    SHIFT_WORK                             = "shift_work"
    WEEKLY_RESIDENT                        = "weekly_resident"
    WEEKLY_RESIDENT_WITH_CAFETERIA         = "weekly_resident_with_cafeteria"
    # Modulo 4 sez. 4.3/4.4: residente settimanale con alloggio dotato di cucina
    WEEKLY_RESIDENT_WITH_KITCHEN           = "weekly_resident_with_kitchen"
    WEEKLY_RESIDENT_WITH_KITCHEN_CAFETERIA = "weekly_resident_with_kitchen_cafeteria"


class Address(BaseModel):
    street: Optional[str] = Field(default=None, max_length=200)
    city: str = Field(..., min_length=1, max_length=100)
    postal_code: str = Field(..., min_length=3, max_length=10)
    country: str = Field(default="CH", min_length=2, max_length=2)

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
        "arcobaleno_zones": 3,
        "arcobaleno_class": "2",
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
    arcobaleno_zones: Optional[int] = Field(default=None, ge=1, le=8, description="Numero zone Arcobaleno (1-7, usa 8 per da 8 zone). Solo per transport_mode=public_transport.")
    arcobaleno_class: str = Field(default="2", pattern=r"^[12]$", description="Classe abbonamento ARCOBALENO: '1' = prima classe, '2' = seconda classe.")
    annual_net_salary_chf: Optional[float] = Field(default=None, ge=0.0)

    employer_pays_transport: bool = Field(default=False)
    employer_has_cafeteria: bool = Field(default=False)
    company_car_monthly_chf: Optional[float] = Field(default=None, ge=0.0)

    # Alloggio residente settimanale (Modulo 4 sez. 4.1 / 4.3)
    annual_accommodation_cost_chf: Optional[float] = Field(default=None, ge=0.0)
    accommodation_type: str = Field(default="without_kitchen", pattern=r"^(without_kitchen|with_kitchen)$")
    accommodation_monthly_chf: Optional[float] = Field(default=None, ge=0.0, description="Costo mensile alloggio (alternativa ad annual_accommodation_cost_chf)")

    include_meals: bool = Field(default=False)
    include_other_expenses: bool = Field(default=False)
    # Spese effettive in sostituzione del forfait IC (Modulo 4 sez. 5.2 / 6.2)
    actual_other_expenses_chf: Optional[float] = Field(default=None, ge=0.0)
    include_secondary_activity: bool = Field(default=False)
    actual_secondary_activity_chf: Optional[float] = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def validate_home_street_required(self) -> DeductionRequest:
        if not self.home_address.street:
            raise ValueError("home_address.street è obbligatorio (via e numero civico del domicilio)")
        return self

    @model_validator(mode="after")
    def validate_arcobaleno_requires_public_transport(self) -> DeductionRequest:
        if self.arcobaleno_zones is not None and self.transport_mode != TransportMode.PUBLIC_TRANSPORT:
            raise ValueError("arcobaleno_zones richiede transport_mode=public_transport")
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
