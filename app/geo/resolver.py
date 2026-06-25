"""
Risolve due indirizzi testuali → distanza stradale in km.
Prova swisstopo prima, cade su Nominatim se fallisce.
"""
from __future__ import annotations
from typing import Optional, Tuple
from ..schemas.request import Address
from .providers.swisstopo import SwisstopoProvider
from .providers.nominatim import NominatimProvider
from .distance import road_distance_km

_swisstopo = SwisstopoProvider()
_nominatim = NominatimProvider()


async def resolve_distance(
    home: Address, work: Address, road_factor: float = 1.25
) -> Tuple[Optional[float], str, Optional[Tuple[float, float]]]:
    """
    Restituisce (distanza_km, nome_provider, home_coords).
    distanza_km è None se entrambi i provider falliscono.
    home_coords è (lat, lon) oppure None se il geocoding del domicilio fallisce.
    """
    home_str = home.full_address()
    work_str = work.full_address()

    coords_home, provider = await _try_resolve(home_str)
    coords_work, _        = await _try_resolve(work_str, preferred_provider=provider)

    if coords_home is None or coords_work is None:
        return None, "none", coords_home

    km = road_distance_km(*coords_home, *coords_work, factor=road_factor)
    return km, provider, coords_home


async def _try_resolve(address: str, preferred_provider: str | None = None) -> Tuple[Optional[Tuple[float,float]], str]:
    if preferred_provider != "nominatim":
        result = await _swisstopo.resolve(address)
        if result:
            return result, "swisstopo"

    result = await _nominatim.resolve(address)
    if result:
        return result, "nominatim"

    return None, "none"
