"""Acceptatiecriterium 4: twee gebruikers met verschillende voorkeuren krijgen
aantoonbaar verschillende matches op dezelfde gevonden deals.
"""
from __future__ import annotations

import datetime

from app.core.combine import ReturnDeal
from app.core.match import match_user

D1 = datetime.date(2026, 8, 1)
D2 = datetime.date(2026, 8, 4)


def _deal(origin, dest, nights, total, provider="ryanair"):
    return ReturnDeal(
        provider=provider, origin=origin, destination=dest, nights=nights,
        total=total, out_date=D1, in_date=D2, out_price=total / 2, in_price=total / 2,
    )


def test_two_users_get_different_matches(db, make_user):
    deals = [
        _deal("EIN", "BCN", 3, 35.0),
        _deal("NRN", "AGP", 3, 80.0),
        _deal("EIN", "FAO", 5, 45.0),
    ]
    # A: alleen EIN, drempel 40 → BCN (35) wel, FAO (45) niet, AGP (NRN) niet gekozen
    user_a = make_user(origins=["EIN"], threshold=40)
    # B: EIN+NRN, drempel 100 → alle drie
    user_b = make_user(origins=["EIN", "NRN"], threshold=100)

    match_a = match_user(db, user_a, deals)
    match_b = match_user(db, user_b, deals)

    assert {(d.origin, d.destination) for d in match_a} == {("EIN", "BCN")}
    assert {(d.origin, d.destination) for d in match_b} == {
        ("EIN", "BCN"), ("NRN", "AGP"), ("EIN", "FAO"),
    }
    assert match_a != match_b


def test_trip_length_filter(db, make_user):
    deals = [_deal("EIN", "BCN", 3, 30.0), _deal("EIN", "BCN", 7, 30.0)]
    user = make_user(origins=["EIN"], threshold=50, trip_lengths=[3])
    matched = match_user(db, user, deals)
    assert [d.nights for d in matched] == [3]


def test_whitelist_and_blacklist(db, make_user):
    deals = [_deal("EIN", "BCN", 3, 30.0), _deal("EIN", "AGP", 3, 30.0)]

    wl_user = make_user(origins=["EIN"], mode="whitelist", dest_whitelist=["BCN"])
    assert {d.destination for d in match_user(db, wl_user, deals)} == {"BCN"}

    bl_user = make_user(origins=["EIN"], mode="blacklist", dest_blacklist=["AGP"])
    assert {d.destination for d in match_user(db, bl_user, deals)} == {"BCN"}


def test_country_filter(db, make_user):
    # BCN/AGP liggen in 'es' (Spanje); FAO in 'pt' (Portugal) volgens de seed.
    deals = [_deal("EIN", "BCN", 3, 30.0), _deal("EIN", "FAO", 3, 30.0)]
    es_user = make_user(origins=["EIN"], mode="country", dest_countries=["es"])
    assert {d.destination for d in match_user(db, es_user, deals)} == {"BCN"}
