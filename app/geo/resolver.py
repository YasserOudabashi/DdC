"""
Risolve due indirizzi testuali → distanza stradale in km.
Prova swisstopo prima, cade su Nominatim se fallisce.
"""
from __future__ import annotations
from typing import Optional, Tuple
from ..schemas.request import Address
from .providers.swisstopo import SwisstopoProvider
from .providers.nominatim import NominatimProvider
from .providers.base import GeoResolved
from .distance import road_distance_km

_swisstopo = SwisstopoProvider()
_nominatim = NominatimProvider()


async def resolve_distance(
    home: Address, work: Address, road_factor: float = 1.25
) -> Tuple[
    Optional[float], str,
    Optional[Tuple[float, float]], Optional[Tuple[float, float]],
    Optional[GeoResolved], Optional[GeoResolved],
]:
    """
    Restituisce (distanza_km, nome_provider, home_coords, work_coords,
    home_resolved, work_resolved).
    distanza_km è None se entrambi i provider falliscono.
    home_resolved/work_resolved contengono PLZ/città risolti per la validazione NPA
    (possono essere None se il provider non li espone).
    """
    home_str = home.full_address()
    work_str = work.full_address()

    home_detail, provider = await _try_resolve(home_str)
    work_detail, _        = await _try_resolve(work_str, preferred_provider=provider)

    coords_home = (home_detail.lat, home_detail.lon) if home_detail else None
    coords_work = (work_detail.lat, work_detail.lon) if work_detail else None

    if coords_home is None or coords_work is None:
        return None, "none", coords_home, coords_work, home_detail, work_detail

    km = road_distance_km(*coords_home, *coords_work, factor=road_factor)
    return km, provider, coords_home, coords_work, home_detail, work_detail


async def _try_resolve(
    address: str, preferred_provider: str | None = None
) -> Tuple[Optional[GeoResolved], str]:
    if preferred_provider != "nominatim":
        result = await _swisstopo.resolve_detailed(address)
        if result:
            return result, "swisstopo"

    result = await _nominatim.resolve_detailed(address)
    if result:
        return result, "nominatim"

    return None, "none"
