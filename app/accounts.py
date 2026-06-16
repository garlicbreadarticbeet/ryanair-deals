"""Account- en onboarding-service: gebruikers, kanalen en voorkeuren.

Wordt gebruikt door zowel de bot (Telegram /start + voorkeur-commando's) als de web-API
(e-mail magic-link + voorkeuren). Houdt de DB-mutaties op één plek.
"""
from __future__ import annotations

import datetime
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import gating
from app.db.models import Channel, Preference, Provider, User, UserOrigin
from app.errors import PremiumRequired
from app.settings import settings
from app.web import auth


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _default_preference(user_id: int) -> Preference:
    return Preference(
        user_id=user_id,
        threshold=Decimal(str(settings.default_threshold)),
        months_ahead=settings.default_months_ahead,
        currency=settings.currency,
        trip_lengths=settings.default_trip_length_list,
        alert_mode="instant",
        dest_filter_mode="all",
    )


def create_user(session: Session, *, email: str | None = None, tier: str = "free") -> User:
    """Nieuwe actieve gebruiker met standaard-voorkeuren."""
    user = User(status="active", tier=tier, email=email)
    session.add(user)
    session.flush()
    session.add(_default_preference(user.id))
    session.flush()
    return user


# ---------- Telegram-onboarding ----------

def get_or_create_telegram_user(session: Session, chat_id: int | str) -> tuple[User, bool]:
    """Vind de gebruiker achter deze Telegram-chat, of maak er één (verifieerd + opt-in).

    Geeft (user, aangemaakt?) terug. /start zonder deeplink-token loopt hierlangs.
    """
    chat_id = str(chat_id)
    channel = session.execute(
        select(Channel).where(Channel.type == "telegram", Channel.address == chat_id)
    ).scalar_one_or_none()
    if channel is not None:
        return session.get(User, channel.user_id), False

    user = create_user(session)
    session.add(
        Channel(user_id=user.id, type="telegram", address=chat_id,
                verified=True, opted_in_at=_now(), enabled=True)
    )
    session.flush()
    return user, True


def link_telegram(session: Session, token_raw: str, chat_id: int | str) -> User | None:
    """Koppel een Telegram-chat aan een bestaand account via een /start-deeplink-token."""
    token = auth.consume_token(session, token_raw, "telegram_link")
    if token is None or token.user_id is None:
        return None
    chat_id = str(chat_id)
    channel = session.execute(
        select(Channel).where(Channel.type == "telegram", Channel.address == chat_id)
    ).scalar_one_or_none()
    if channel is None:
        session.add(
            Channel(user_id=token.user_id, type="telegram", address=chat_id,
                    verified=True, opted_in_at=_now(), enabled=True)
        )
    else:
        channel.user_id = token.user_id
        channel.verified = True
        channel.opted_in_at = _now()
        channel.enabled = True
    session.flush()
    return session.get(User, token.user_id)


# ---------- E-mail magic-link ----------

def start_email_login(session: Session, email: str) -> str:
    """Maak (zo nodig) een account + e-mailkanaal en geef een magic-link-token terug.

    De caller verstuurt het token als link (web). Het e-mailkanaal is nog niet geverifieerd.
    """
    email = email.strip().lower()
    user = session.execute(
        select(User).where(func.lower(User.email) == email)
    ).scalar_one_or_none()
    if user is None:
        user = create_user(session, email=email)
    channel = session.execute(
        select(Channel).where(Channel.type == "email", Channel.address == email)
    ).scalar_one_or_none()
    if channel is None:
        session.add(Channel(user_id=user.id, type="email", address=email, verified=False, enabled=True))
        session.flush()
    return auth.issue_token(session, "email_login", user_id=user.id, payload=email)


def complete_email_login(session: Session, token_raw: str) -> tuple[User, str] | None:
    """Verbruik een magic-link-token: verifieer e-mail + kanaal, geef (user, sessietoken)."""
    token = auth.consume_token(session, token_raw, "email_login")
    if token is None or token.user_id is None:
        return None
    user = session.get(User, token.user_id)
    user.email_verified = True
    channel = session.execute(
        select(Channel).where(Channel.type == "email", Channel.address == token.payload)
    ).scalar_one_or_none()
    if channel is not None:
        channel.verified = True
        channel.opted_in_at = _now()
    session.flush()
    session_token = auth.issue_token(session, "session", user_id=user.id)
    return user, session_token


# ---------- Voorkeuren ----------

def set_threshold(session: Session, user: User, value: float) -> None:
    user.preferences.threshold = Decimal(str(value))
    session.flush()


def set_trip_lengths(session: Session, user: User, lengths: Sequence[int]) -> None:
    user.preferences.trip_lengths = list(lengths)
    session.flush()


def set_origins(session: Session, user: User, provider_code: str, iatas: Sequence[str]) -> None:
    """Vervang de vertrekvelden van deze gebruiker voor één provider.

    Handhaaft de gratis-limiet (gating.max_origins): raised PremiumRequired bij overschrijding.
    """
    iatas = [i.upper() for i in iatas]
    limit = gating.max_origins(user)
    if len(set(iatas)) > limit:
        raise PremiumRequired(
            f"Met een gratis account kun je max {limit} vertrekveld(en) kiezen. "
            "Upgrade naar premium voor meer."
        )
    provider_id = session.execute(
        select(Provider.id).where(Provider.code == provider_code)
    ).scalar_one()
    # Verse query i.p.v. user.origins (dat kan stale zijn na eerdere mutaties).
    existing = session.execute(
        select(UserOrigin).where(
            UserOrigin.user_id == user.id, UserOrigin.provider_id == provider_id
        )
    ).scalars().all()
    for origin in existing:
        session.delete(origin)
    session.flush()
    for iata in iatas:
        session.add(UserOrigin(user_id=user.id, provider_id=provider_id, origin_iata=iata.upper()))
    session.flush()
    session.expire(user, ["origins"])


def delete_account(session: Session, user: User) -> None:
    """GDPR: verwijder de gebruiker (cascade ruimt alles op)."""
    from app.db import repo

    repo.delete_user(session, user.id)
