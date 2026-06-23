from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Tuple


class GeoProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def resolve(self, address: str) -> Optional[Tuple[float, float]]:
        """Restituisce (lat, lon) o None se non trovato."""
        ...
