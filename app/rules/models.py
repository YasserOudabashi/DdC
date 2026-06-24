from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class PublicTransportRule(BaseModel):
    mode: str
    cap_chf: Optional[float]


class PrivateCarRule(BaseModel):
    rate_chf_per_km: Optional[float] = None
    cap_chf: Optional[float]
    condition: Optional[str] = None


class MotorcycleRule(BaseModel):
    rate_chf_per_km: float


class BicycleRule(BaseModel):
    flat_rate_chf_per_year: float


class TransportRules(BaseModel):
    public_transport: PublicTransportRule
    private_car: PrivateCarRule
    bicycle: BicycleRule
    motorcycle_white_plate: Optional[MotorcycleRule] = None


class MealRule(BaseModel):
    rate_chf_per_day: float
    annual_max_chf: float


class AccommodationRule(BaseModel):
    mode: str                                # "actual_cost"
    cap_chf: Optional[float]


class MealsRules(BaseModel):
    without_cafeteria: MealRule              # Art. 6 cpv. 1 — deduzione intera
    with_cafeteria: MealRule                 # Art. 6 cpv. 2 — mezza deduzione (con mensa)
    shift_work: Optional[MealRule] = None    # lavori a turni — CHF 15/giorno, max 3'200
    weekly_resident: MealRule                # Art. 9 cpv. 2 — soggiorno fuori domicilio
    weekly_resident_with_cafeteria: MealRule # Art. 9 + 6 cpv. 2 — residente settimanale con mensa
    weekly_resident_accommodation: Optional[AccommodationRule] = None  # alloggio 1 camera, costo effettivo


class SecondaryActivityRule(BaseModel):
    method: str                              # "flat_rate_or_actual" | "percentage_of_net_salary"
    flat_rate_chf: Optional[float] = None    # IC: forfait CHF 800
    rate_percent: Optional[float] = None     # IFD: 20% salario netto
    minimum_chf: Optional[float] = None      # IFD: min CHF 800
    maximum_chf: Optional[float] = None      # IFD: max CHF 2'400


class OtherExpensesRule(BaseModel):
    method: str                              # "flat_rate" | "percentage_of_net_salary"
    flat_rate_chf: Optional[float] = None    # usato quando method="flat_rate" (cantonale TI)
    flat_rate_part_time_chf: Optional[float] = None  # riduzione per part-time <50% o <6 mesi
    rate_percent: Optional[float] = None     # usato quando method="percentage_of_net_salary" (IFD)
    minimum_chf: Optional[float] = None
    maximum_chf: Optional[float] = None
    secondary_activity: Optional[SecondaryActivityRule] = None  # attività accessoria dipendente


class TaxLevelRules(BaseModel):
    transport: TransportRules
    meals: MealsRules
    other_expenses: OtherExpensesRule


class CantonalRules(TaxLevelRules):
    flat_rate_all_expenses_chf: Optional[float] = None


class WorkingDaysConfig(BaseModel):
    standard_annual: int


class GeocodingConfig(BaseModel):
    road_correction_factor: float = 1.25


class FiscalYearRules(BaseModel):
    version: str
    authority_reference: dict
    cantonal_TI: CantonalRules
    federal_IFD: TaxLevelRules
    working_days: WorkingDaysConfig
    geocoding: GeocodingConfig = GeocodingConfig()
