"""Maandhorizon-helper — provider-onafhankelijke port van deals.months_in_horizon().

Levert de lijst 'YYYY-MM-01'-strings die de zoekhorizon (+ de langste reisduur) raakt,
zoals het cheapestPerDay-endpoint per maand verwacht.
"""
from __future__ import annotations

import datetime
from collections.abc import Sequence


def months_in_horizon(
    months_ahead: int,
    trip_lengths: Sequence[int],
    today: datetime.date | None = None,
) -> list[str]:
    """Lijst van 'YYYY-MM-01' die de horizon (+ langste reis) raakt.

    Identiek aan de oude deals.months_in_horizon(), maar met expliciete argumenten
    (was: config.MONTHS_AHEAD / config.TRIP_LENGTHS) zodat het testbaar en per-scan
    parametriseerbaar is.
    """
    today = today or datetime.date.today()
    start = today.replace(day=1)
    end = today + datetime.timedelta(days=int(months_ahead * 30.5) + max(trip_lengths))
    months, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append(f"{y:04d}-{m:02d}-01")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return months
