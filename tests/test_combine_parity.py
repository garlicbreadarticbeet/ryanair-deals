"""No-regression: app.core.combine.best_returns == de bewezen deals.best_returns.

Dit is het bewijs dat de verplaatsing naar de provider-onafhankelijke laag het gedrag
niet verandert. Geen DB en geen netwerk nodig — pure functie-equivalentie, zowel op een
vast scenario als gerandomiseerd over veel inputs (incl. datums vóór 'today' om de
horizonfilter te raken).
"""
from __future__ import annotations

import datetime
import random

import config
import deals
from app.core.combine import best_returns as new_best_returns
from app.providers.base import DailyFare

TODAY = datetime.date(2026, 6, 16)
HORIZON_END = TODAY + datetime.timedelta(days=int(config.MONTHS_AHEAD * 30.5))


def _to_fares(per_day: dict, origin: str, destination: str) -> list[DailyFare]:
    """Zet een fetch_perday-dict {date:(price,dep)} om naar DailyFare-lijst (zelfde volgorde)."""
    return [
        DailyFare(provider="p", origin=origin, destination=destination,
                  fly_date=dt, price=price, currency="EUR", departure=dep)
        for dt, (price, dep) in per_day.items()
    ]


def _assert_equivalent(outbound: dict, inbound: dict) -> None:
    old = deals.best_returns(outbound, inbound, TODAY, HORIZON_END)
    new_list = new_best_returns(
        _to_fares(outbound, "A", "B"),
        _to_fares(inbound, "B", "A"),
        config.TRIP_LENGTHS, TODAY, HORIZON_END,
    )
    new = {d.nights: d for d in new_list}

    assert set(old) == set(new)
    for n, rec in old.items():
        nd = new[n]
        assert rec["total"] == nd.total
        assert rec["out_date"] == nd.out_date.isoformat()
        assert rec["in_date"] == nd.in_date.isoformat()
        assert rec["out_price"] == nd.out_price
        assert rec["in_price"] == nd.in_price


def test_combine_matches_legacy_fixed_scenario():
    """Vast scenario met meerdere kandidaten per reisduur en een goedkoper alternatief."""
    base = TODAY
    outbound = {
        base + datetime.timedelta(days=2): (39.99, "dep1"),
        base + datetime.timedelta(days=3): (19.99, "dep2"),   # goedkopere heen
        base + datetime.timedelta(days=10): (24.50, "dep3"),
    }
    inbound = {
        base + datetime.timedelta(days=5): (15.00, "dep4"),   # +3 vanaf dag2, +2 vanaf dag3
        base + datetime.timedelta(days=6): (12.00, "dep5"),   # +3 vanaf dag3
        base + datetime.timedelta(days=13): (40.00, "dep6"),  # +3 vanaf dag10
        base + datetime.timedelta(days=17): (10.00, "dep7"),  # +7 vanaf dag10
    }
    _assert_equivalent(outbound, inbound)


def test_combine_matches_legacy_randomized():
    """200 willekeurige scenario's; combine moet exact deals.best_returns reproduceren."""
    window_start = TODAY - datetime.timedelta(days=5)  # ook datums vóór today (horizonfilter)
    for seed in range(200):
        rng = random.Random(seed)

        def rand_dict() -> dict:
            d: dict = {}
            for offset in range(0, 130):
                if rng.random() < 0.45:
                    dt = window_start + datetime.timedelta(days=offset)
                    d[dt] = (round(rng.uniform(5.0, 120.0), 2), f"dep-{offset}")
            return d

        _assert_equivalent(rand_dict(), rand_dict())
