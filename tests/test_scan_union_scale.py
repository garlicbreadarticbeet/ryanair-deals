"""Acceptatiecriterium 2: de scan-unie schaalt met het aantal unieke (provider, origin)-
paren, NIET met het aantal gebruikers.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.db import repo
from app.db.models import Preference, Provider, User, UserOrigin


def test_deduped_union_independent_of_user_count(db):
    ryanair_id = db.execute(select(Provider.id).where(Provider.code == "ryanair")).scalar_one()

    # 50 gebruikers die ALLEMAAL EIN + NRN kiezen.
    for _ in range(50):
        user = User(status="active", tier="free")
        db.add(user)
        db.flush()
        db.add(Preference(user_id=user.id, threshold=Decimal("50"), trip_lengths=[3, 5, 7]))
        db.add(UserOrigin(user_id=user.id, provider_id=ryanair_id, origin_iata="EIN"))
        db.add(UserOrigin(user_id=user.id, provider_id=ryanair_id, origin_iata="NRN"))
    db.flush()

    targets = repo.deduped_origin_targets(db)

    # 100 user-origin-rijen, maar slechts 2 unieke scan-doelen.
    assert set(targets) == {("ryanair", "EIN"), ("ryanair", "NRN")}
    assert len(targets) == 2


def test_inactive_users_and_disabled_providers_excluded(db):
    ryanair_id = db.execute(select(Provider.id).where(Provider.code == "ryanair")).scalar_one()
    wizz_id = db.execute(select(Provider.id).where(Provider.code == "wizzair")).scalar_one()

    active = User(status="active", tier="free")
    paused = User(status="paused", tier="free")
    db.add_all([active, paused])
    db.flush()
    db.add(Preference(user_id=active.id, threshold=Decimal("50"), trip_lengths=[3]))
    db.add(Preference(user_id=paused.id, threshold=Decimal("50"), trip_lengths=[3]))
    # actieve user: EIN bij ryanair (telt) + BCN bij wizzair (disabled → telt niet)
    db.add(UserOrigin(user_id=active.id, provider_id=ryanair_id, origin_iata="EIN"))
    db.add(UserOrigin(user_id=active.id, provider_id=wizz_id, origin_iata="BCN"))
    # gepauzeerde user: NRN (telt niet, want niet actief)
    db.add(UserOrigin(user_id=paused.id, provider_id=ryanair_id, origin_iata="NRN"))
    db.flush()

    targets = set(repo.deduped_origin_targets(db))
    assert targets == {("ryanair", "EIN")}
