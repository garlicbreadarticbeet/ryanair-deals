"""Wizz Air-adapter — STUB voor Fase 2.

Bewijst acceptatiecriterium 1/regel 5 structureel: de naad bestaat naast Ryanair zonder
dat combine/match/notify iets van Wizz weten. De provider staat in de registry maar in de
DB op enabled=false, dus de scan raakt hem niet tot de TODO af is.
"""
from __future__ import annotations

import datetime
from collections.abc import Iterable, Sequence

from app.providers.base import DailyFare, Route
from app.providers.registry import register


@register
class WizzAirProvider:
    """Stub-adapter voor Wizz Air (provider-code 'wizzair')."""

    code = "wizzair"

    def discover_routes(
        self,
        origins: Sequence[str],
        date_from: datetime.date,
        date_to: datetime.date,
        destination_country: str | None = None,
    ) -> Iterable[Route]:
        # TODO(provider): Wizz Air route-discovery via hun publieke timetable/availability-API.
        #   Moet Route(provider='wizzair', ...) leveren. Netwerk via requests + certifi (base.get_session).
        return []

    def daily_fares(
        self,
        origin: str,
        destination: str,
        months: Sequence[str],
        currency: str,
    ) -> Iterable[DailyFare]:
        # TODO(provider): Wizz cheapest-per-day-equivalent -> DailyFare. Geen ryanair-py; requests + certifi.
        return []
