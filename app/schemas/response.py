from __future__ import annotations
from typing import Optional, List
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import BaseModel, Field


class Coordinates(BaseModel):
    lat: float
    lon: float


class DeductionLine(BaseModel):
    label: str
    amount_chf: float
    basis: str                           # es. "CHF 0.75/km × 32.4km × 2 × 220 giorni"
    legal_reference: str                 # es. "Art. 25 cpv. 1a LT"
    capped: bool = False
    cap_amount_chf: Optional[float] = None


class TransportResult(BaseModel):
    mode: str
    one_way_distance_km: Optional[float] = None
    effective_working_days: int
    gross_deduction_chf: float
    net_deduction_chf: float             # dopo l'applicazione del cap
    lines: List[DeductionLine] = []


class TaxLevelResult(BaseModel):
    level: str                           # "cantonal_TI" | "federal_IFD"
    transport_deduction: TransportResult
    # Scenario alternativo "auto fino alla stazione + abbonamento" mostrato quando
    # la deduzione auto privata è stata bloccata perché i mezzi pubblici erano usabili.
    alternative_transport: Optional[TransportResult] = None
    meals_deduction_chf: Optional[float] = None
    meals_basis_text: Optional[str] = None
    accommodation_deduction_chf: Optional[float] = None
    other_expenses_deduction_chf: Optional[float] = None
    secondary_activity_deduction_chf: Optional[float] = None
    total_deduction_chf: float
    flat_rate_applied: bool = False      # True se usato il forfait invece delle spese effettive
    flat_rate_chf: Optional[float] = None
    notes: List[str] = []


class AddressCheck(BaseModel):
    """Esito della validazione NPA ↔ indirizzo risolto dal geocoder."""
    field: str                           # "home" | "work" | "spouse_home" | "spouse_work"
    input_npa: str
    resolved_npa: Optional[str] = None
    input_city: Optional[str] = None
    resolved_city: Optional[str] = None
    matched: bool = True


class SpouseResult(BaseModel):
    cantonal_TI: TaxLevelResult
    federal_IFD: TaxLevelResult
    distance_km: Optional[float] = None
    geocoding_used: bool = False
    home_coordinates: Optional[Coordinates] = None
    work_coordinates: Optional[Coordinates] = None
    warnings: List[str] = []


class DeductionResponse(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fiscal_year: int
    rules_version: str                   # versione del YAML usato

    cantonal_TI: TaxLevelResult
    federal_IFD: TaxLevelResult

    geocoding_used: bool = False
    geocoding_provider: Optional[str] = None
    distance_km: Optional[float] = None  # distanza calcolata o fornita manualmente

    home_coordinates: Optional[Coordinates] = None
    work_coordinates: Optional[Coordinates] = None

    spouse: Optional[SpouseResult] = None

    address_validation: List[AddressCheck] = []  # validazione NPA ↔ città/via

    warnings: List[str] = []            # es. "frontaliere: verificare accordo I-CH 2024"
    errors: List[str] = []
