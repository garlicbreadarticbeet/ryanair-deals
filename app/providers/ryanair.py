"""Ryanair-adapter — pakt de bewezen logica uit deals.py in achter het FlightProvider-contract.

- ``discover_routes`` wrapt ryanair-py's ``get_cheapest_flights`` (route-ontdekking).
- ``daily_fares`` is de letterlijke port van ``fetch_perday`` (farfnd/v4 cheapestPerDay),
  maar yield't genormaliseerde DailyFare-objecten i.p.v. een dict.

De oude per-user filters (ONLY/EXCLUDE/DESTINATION_COUNTRY) zitten hier BEWUST NIET in;
die zijn nu per gebruiker en horen in app/core/match.py. Netwerk via requests + certifi.
"""
from __future__ import annotations

import datetime
from collections.abc import Iterable, Sequence

from ryanair import Ryanair

from app.providers.base import DailyFare, Route, get_session
from app.providers.registry import register
from app.settings import settings

_FARE_BASE = "https://services-api.ryanair.com/farfnd/v4/oneWayFares"


@register
class RyanairProvider:
    """Adapter voor Ryanair (provider-code 'ryanair')."""

    code = "ryanair"

    def __init__(self) -> None:
        # Fase 1 is EUR-only; ryanair-py wil de valuta bij constructie weten.
        self._api = Ryanair(currency=settings.currency)
        self._session = get_session()

    def discover_routes(
        self,
        origins: Sequence[str],
        date_from: datetime.date,
        date_to: datetime.date,
        destination_country: str | None = None,
    ) -> Iterable[Route]:
        """Ontdek bestemmingen per vertrekveld via get_cheapest_flights.

        Tolerant per origin: een fout op één vertrekveld stopt de rest niet (zoals scan()).
        """
        routes: list[Route] = []
        for origin in origins:
            try:
                flights = self._api.get_cheapest_flights(
                    origin, date_from, date_to, destination_country=destination_country
                )
            except Exception:
                flights = []
            seen: set[str] = set()
            for f in flights:
                dest = f.destination
                if dest in seen:
                    continue
                seen.add(dest)
                routes.append(
                    Route(
                        provider=self.code,
                        origin=f.origin,
                        destination=dest,
                        origin_name=f.originFull,
                        destination_name=f.destinationFull,
                    )
                )
        return routes

    def daily_fares(
        self,
        origin: str,
        destination: str,
        months: Sequence[str],
        currency: str,
    ) -> Iterable[DailyFare]:
        """Enkele-richting dagprijzen — letterlijke port van fetch_perday()."""
        out: list[DailyFare] = []
        for month in months:
            url = f"{_FARE_BASE}/{origin}/{destination}/cheapestPerDay"
            try:
                r = self._session.get(
                    url,
                    params={"outboundMonthOfDate": month, "currency": currency},
                    timeout=20,
                )
                if r.status_code != 200:
                    continue
                fares = r.json().get("outbound", {}).get("fares", [])
            except Exception:
                continue
            for f in fares:
                p = f.get("price")
                if not p or f.get("soldOut") or f.get("unavailable"):
                    continue
                try:
                    d = datetime.date.fromisoformat(f["day"])
                except Exception:
                    continue
                out.append(
                    DailyFare(
                        provider=self.code,
                        origin=origin,
                        destination=destination,
                        fly_date=d,
                        price=float(p["value"]),
                        currency=currency,
                        departure=f.get("departureDate"),
                    )
                )
        return out
