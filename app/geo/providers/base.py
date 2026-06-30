from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class GeoResolved:
    """Risultato dettagliato del geocoding: coordinate + componenti dell'indirizzo
    effettivamente risolto dal provider (usati per validare l'NPA inserito)."""
    lat: float
    lon: float
    postcode: Optional[str] = None
    city: Optional[str] = None


class GeoProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def resolve(self, address: str) -> Optional[Tuple[float, float]]:
        """Restituisce (lat, lon) o None se non trovato."""
        ...

    async def resolve_detailed(self, address: str) -> Optional[GeoResolved]:
        """Restituisce coordinate + componenti risolti (PLZ/città), o None.

        Default: usa resolve() e non popola i componenti (postcode/city = None),
        così la validazione NPA viene semplicemente saltata. I provider concreti
        sovrascrivono per fornire i dettagli."""
        coords = await self.resolve(address)
        if coords is None:
            return None
        return GeoResolved(lat=coords[0], lon=coords[1])
