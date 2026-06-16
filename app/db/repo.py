"""Query-helpers zodat core/ geen rauwe SQL bevat.

Bevat o.a. de gededupte (provider, origin)-unie (de kern van "scan schaalt niet met
het aantal gebruikers"), de deals-upsert en het GDPR-delete-pad.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import Airport, Deal, Preference, Provider, User, UserOrigin


def deduped_origin_targets(session: Session) -> list[tuple[str, str]]:
    """(provider_code, origin_iata) — de gededupte unie over alle actieve gebruikers.

    SELECT DISTINCT in de DB: O(unieke origins), NIET O(gebruikers). 10.000 gebruikers
    die EIN+NRN kiezen → 2 paren → 2 discovery-calls.
    """
    rows = session.execute(
        select(Provider.code, UserOrigin.origin_iata)
        .join(UserOrigin, UserOrigin.provider_id == Provider.id)
        .join(User, User.id == UserOrigin.user_id)
        .where(User.status == "active", Provider.enabled.is_(True))
        .distinct()
    ).all()
    return [(code, iata) for code, iata in rows]


def union_trip_lengths(session: Session) -> list[int]:
    """Unie van alle gekozen reisduren over actieve gebruikers (klein; in-memory unie)."""
    arrays = session.execute(
        select(Preference.trip_lengths)
        .join(User, User.id == Preference.user_id)
        .where(User.status == "active")
    ).scalars().all()
    out: set[int] = set()
    for arr in arrays:
        out.update(arr or [])
    return sorted(out)


def max_months_ahead(session: Session) -> int | None:
    """Verste horizon over actieve gebruikers (scan dekt de breedst-kijkende user)."""
    return session.execute(
        select(func.max(Preference.months_ahead))
        .join(User, User.id == Preference.user_id)
        .where(User.status == "active")
    ).scalar()


def upsert_deal(
    session: Session,
    *,
    provider: str,
    origin: str,
    destination: str,
    nights: int,
    out_date: datetime.date,
    in_date: datetime.date,
    out_price: float,
    in_price: float,
    total_price: float,
    currency: str,
) -> None:
    """Upsert één markt-deal (ON CONFLICT op de unieke combinatie → prijs + last_seen bij)."""
    values = {
        "provider": provider,
        "origin": origin,
        "destination": destination,
        "nights": nights,
        "out_date": out_date,
        "in_date": in_date,
        "out_price": Decimal(str(out_price)),
        "in_price": Decimal(str(in_price)),
        "total_price": Decimal(str(total_price)),
        "currency": currency,
    }
    stmt = pg_insert(Deal).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_deals_combo",
        set_={
            "out_price": stmt.excluded.out_price,
            "in_price": stmt.excluded.in_price,
            "total_price": stmt.excluded.total_price,
            "currency": stmt.excluded.currency,
            "last_seen": func.now(),
        },
    )
    session.execute(stmt)


def destination_countries(session: Session, iatas: set[str]) -> dict[str, str]:
    """Map IATA → alpha-2 landcode voor het land-bestemmingsfilter."""
    if not iatas:
        return {}
    rows = session.execute(
        select(Airport.iata, Airport.country_code).where(Airport.iata.in_(iatas))
    ).all()
    return {iata: cc for iata, cc in rows}


def allowed_provider_origins(session: Session, user_id: int) -> set[tuple[str, str]]:
    """De (provider_code, origin)-paren die deze gebruiker heeft gekozen."""
    rows = session.execute(
        select(Provider.code, UserOrigin.origin_iata)
        .join(Provider, Provider.id == UserOrigin.provider_id)
        .where(UserOrigin.user_id == user_id)
    ).all()
    return {(code, iata) for code, iata in rows}


def deals_for_origins(session: Session, pairs: set[tuple[str, str]]) -> list[Deal]:
    """Markt-deals voor de gegeven (provider_code, origin)-paren (voor /deals uit de DB)."""
    if not pairs:
        return []
    origins = {iata for _, iata in pairs}
    rows = session.execute(select(Deal).where(Deal.origin.in_(origins))).scalars().all()
    return [d for d in rows if (d.provider, d.origin) in pairs]


def delete_user(session: Session, user_id: int) -> None:
    """GDPR: verwijder de gebruiker; ON DELETE CASCADE ruimt prefs/channels/origins/
    sent_alerts/auth_tokens mee op."""
    session.execute(delete(User).where(User.id == user_id))
