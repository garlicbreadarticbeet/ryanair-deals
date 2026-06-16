"""Onboarding-service: Telegram-start/koppeling, e-mail magic-link, voorkeuren."""
from __future__ import annotations

from sqlalchemy import func, select

from app import accounts
from app.db.models import Channel, User, UserOrigin
from app.web import auth


def test_telegram_get_or_create_is_idempotent(db):
    user, created = accounts.get_or_create_telegram_user(db, 5551)
    assert created is True
    assert user.preferences is not None  # standaard-voorkeuren aangemaakt
    channel = db.execute(
        select(Channel).where(Channel.user_id == user.id, Channel.type == "telegram")
    ).scalar_one()
    assert channel.address == "5551"
    assert channel.verified and channel.opted_in_at is not None

    again, created2 = accounts.get_or_create_telegram_user(db, 5551)
    assert created2 is False and again.id == user.id


def test_link_telegram_via_deeplink(db, make_user):
    user = make_user()
    token = auth.issue_token(db, "telegram_link", user_id=user.id)
    linked = accounts.link_telegram(db, token, 7777)
    assert linked is not None and linked.id == user.id
    channel = db.execute(
        select(Channel).where(Channel.address == "7777", Channel.type == "telegram")
    ).scalar_one()
    assert channel.user_id == user.id and channel.verified


def test_email_magic_link_flow(db):
    raw = accounts.start_email_login(db, "Reiziger@Example.NL")

    user = db.execute(
        select(User).where(func.lower(User.email) == "reiziger@example.nl")
    ).scalar_one()
    channel = db.execute(
        select(Channel).where(Channel.type == "email", Channel.address == "reiziger@example.nl")
    ).scalar_one()
    assert channel.verified is False  # nog niet bevestigd

    result = accounts.complete_email_login(db, raw)
    assert result is not None
    verified_user, session_token = result
    assert verified_user.id == user.id and verified_user.email_verified is True
    assert channel.verified is True and channel.opted_in_at is not None
    assert auth.verify_session(db, session_token) == user.id


def test_set_origins_replaces(db):
    user, _ = accounts.get_or_create_telegram_user(db, 9001)

    accounts.set_origins(db, user, "ryanair", ["ein", "nrn"])  # lowercase → uppercase
    origins = set(
        db.execute(select(UserOrigin.origin_iata).where(UserOrigin.user_id == user.id)).scalars()
    )
    assert origins == {"EIN", "NRN"}

    accounts.set_origins(db, user, "ryanair", ["AMS"])
    origins = set(
        db.execute(select(UserOrigin.origin_iata).where(UserOrigin.user_id == user.id)).scalars()
    )
    assert origins == {"AMS"}  # vervangen, niet toegevoegd
