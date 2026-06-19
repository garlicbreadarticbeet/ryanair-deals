"""Maatschappij-agnostisch contract: genormaliseerde types + de FlightProvider-interface.

Dit is het ENIGE wat app/core/ van providers mag kennen. core/ importeert nooit een
concrete adapter of een maatschappij-specifiek type. Een nieuwe maatschappij implementeert
dit Protocol in één nieuw bestand onder app/providers/.
"""
from __future__ import annotations

import datetime
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.net import get_session  # re-export: netwerk via requests + certifi


@dataclass(frozen=True)
class DailyFare:
    """Eén enkele-richting dagprijs — de genormaliseerde tegenhanger van de oude
    fetch_perday-waarde ``{date: (price, departure)}``.

    ``price`` is een float (spiegelt de bron); de DB-laag converteert naar NUMERIC(8,2).
    """

    provider: str
    origin: str
    destination: str
    fly_date: datetime.date
    price: float
    currency: str
    departure: str | None = None        # ISO-vertrektijd uit de bron (voor latere deeplinks)


@dataclass(frozen=True)
class Route:
    """Een door een provider ontdekte directionele route (origin -> destination)."""

    provider: str
    origin: str
    destination: str
    origin_name: str | None = None
    destination_name: str | None = None
    destination_country: str | None = None   # alpha-2, indien de provider het levert


@dataclass(frozen=True)
class ReturnFare:
    """Een retour-native prijs: heen+terug als één geheel, zoals gecachte aggregators
    (Travelpayouts) die leveren. Onderscheidt zich van DailyFare (één richting → waar
    core/combine zelf retours van bouwt). Providers die dit leveren implementeren
    ``return_deals`` (zie ReturnFareProvider); de scan slaat ze direct op als deal.

    ``deeplink`` is de (affiliate-)boekingslink; ``airline`` een leesbare naam voor de alert.
    """

    provider: str
    origin: str
    destination: str
    nights: int
    out_date: datetime.date
    in_date: datetime.date
    total: float
    currency: str
    deeplink: str | None = None
    airline: str | None = None


@runtime_checkable
class FlightProvider(Protocol):
    """Interface die elke maatschappij-adapter implementeert.

    De enige twee provider-specifieke methodes; combine/match/notify raken een adapter nooit aan.
    """

    code: str  # == providers.code in de DB én de registry-sleutel

    def discover_routes(
        self,
        origins: Sequence[str],
        date_from: datetime.date,
        date_to: datetime.date,
        destination_country: str | None = None,
    ) -> Iterable[Route]:
        """Ontdek directionele routes vanaf de gegeven vertrekvelden."""
        ...

    def daily_fares(
        self,
        origin: str,
        destination: str,
        months: Sequence[str],
        currency: str,
    ) -> Iterable[DailyFare]:
        """Enkele-richting dagprijzen. ``months`` is een lijst 'YYYY-MM-01'."""
        ...


@runtime_checkable
class ReturnFareProvider(Protocol):
    """Optionele capability voor providers die retours al gecombineerd leveren (de cache
    ís een retour). De scan kiest dit pad als de adapter ``return_deals`` heeft; anders het
    DailyFare-pad. core/match/notify blijven ongemoeid — ze werken op de opgeslagen deals.
    """

    code: str

    def return_deals(
        self,
        origins: Sequence[str],
        today: datetime.date,
        horizon_end: datetime.date,
        trip_lengths: Sequence[int],
        currency: str,
    ) -> Iterable[ReturnFare]:
        """De goedkoopste retours per (origin, destination, reisduur) binnen de horizon."""
        ...


# get_session wordt hierboven uit app.net geïmporteerd en hier re-geëxporteerd, zodat
# bestaande imports (`from app.providers.base import get_session`) blijven werken.
__all__ = ["DailyFare", "Route", "ReturnFare", "FlightProvider", "ReturnFareProvider", "get_session"]
