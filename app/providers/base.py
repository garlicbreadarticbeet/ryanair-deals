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

import certifi
import requests


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


def get_session() -> requests.Session:
    """Gedeelde requests-sessie met certifi-CA's.

    Harde regel: netwerkcalls via requests (+certifi), nooit urllib. Elke adapter die zelf
    HTTP doet, gebruikt deze helper. (NB: ryanair-py beheert zijn eigen requests-sessie voor
    get_cheapest_flights; die is óók requests-based, geen urllib.)
    """
    session = requests.Session()
    session.verify = certifi.where()
    return session
