"""Eenmalige tokens voor onboarding: e-mail magic-link, Telegram /start-deeplink, en een
langer levend web-sessietoken. Tokens worden NOOIT plain opgeslagen — alleen hun sha256.
"""
from __future__ import annotations

import datetime
import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuthToken

# Levensduur per soort (minuten).
_TTL_MINUTES = {
    "email_login": 30,
    "telegram_link": 30,
    "session": 60 * 24 * 30,  # 30 dagen
}


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def issue_token(
    session: Session,
    purpose: str,
    *,
    user_id: int | None = None,
    payload: str | None = None,
    ttl_minutes: int | None = None,
) -> str:
    """Maak een token, sla de hash op, en geef het RUWE token terug (alleen nu zichtbaar)."""
    raw = secrets.token_urlsafe(32)
    ttl = ttl_minutes if ttl_minutes is not None else _TTL_MINUTES[purpose]
    session.add(
        AuthToken(
            token_hash=_hash(raw),
            user_id=user_id,
            purpose=purpose,
            payload=payload,
            expires_at=_now() + datetime.timedelta(minutes=ttl),
        )
    )
    session.flush()
    return raw


def consume_token(session: Session, raw: str, purpose: str) -> AuthToken | None:
    """Valideer + verbruik een eenmalig token. None als onbekend/verlopen/al gebruikt."""
    token = session.execute(
        select(AuthToken).where(AuthToken.token_hash == _hash(raw), AuthToken.purpose == purpose)
    ).scalar_one_or_none()
    if token is None or token.consumed_at is not None:
        return None
    if token.expires_at <= _now():
        return None
    token.consumed_at = _now()
    session.flush()
    return token


def verify_session(session: Session, raw: str) -> int | None:
    """Geef de user_id van een geldig (niet-verlopen) sessietoken; anders None. Niet verbruikend."""
    token = session.execute(
        select(AuthToken).where(AuthToken.token_hash == _hash(raw), AuthToken.purpose == "session")
    ).scalar_one_or_none()
    if token is None or token.expires_at <= _now():
        return None
    return token.user_id
