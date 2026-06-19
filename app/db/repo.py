"""Query-helpers zodat core/ geen rauwe SQL bevat.

Bevat o.a. de gededupte (provider, origin)-unie (de kern van "scan schaalt niet met
het aantal gebruikers"), de deals-upsert en het GDPR-delete-pad.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import (
    Airport,
    Deal,
    DealPricePoint,
    Preference,
    Provider,
    User,
    UserOrigin,
)


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
    airline: str | None = None,
    deeplink: str | None = None,
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
        "airline": airline,
        "deeplink": deeplink,
    }
    stmt = pg_insert(Deal).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_deals_combo",
        set_={
            "out_price": stmt.excluded.out_price,
            "in_price": stmt.excluded.in_price,
            "total_price": stmt.excluded.total_price,
            "currency": stmt.excluded.currency,
            "airline": stmt.excluded.airline,
            "deeplink": stmt.excluded.deeplink,
            "last_seen": func.now(),
        },
    )
    session.execute(stmt)


def search_airports(session: Session, query: str, limit: int = 20) -> list[dict]:
    """Luchthavens die matchen op code, naam of stad — voor de zoek-en-kies UI.

    Origin-seeds (de NL/grensvelden) eerst, daarna alfabetisch. Code-match (begint met)
    weegt zwaar zodat 'EIN' meteen Eindhoven bovenaan zet.
    """
    q = query.strip().lower()
    if not q:
        return []
    code_match = func.lower(Airport.iata).like(f"{q}%")
    rows = session.execute(
        select(Airport.iata, Airport.name, Airport.city, Airport.country_code)
        .where(or_(code_match, func.lower(Airport.name).like(f"%{q}%"),
                   func.lower(Airport.city).like(f"%{q}%")))
        .order_by(code_match.desc(), Airport.is_origin_seed.desc(), Airport.name)
        .limit(limit)
    ).all()
    return [
        {"iata": i, "name": n, "city": c, "country": cc,
         "label": f"{n} ({i})" if (c or n) == n else f"{c} – {n} ({i})"}
        for i, n, c, cc in rows
    ]


def airport_labels(session: Session, iatas) -> dict[str, str]:
    """Map IATA → 'Naam (IATA)' voor het tonen van al-gekozen luchthavens als chips."""
    iatas = list(iatas)
    if not iatas:
        return {}
    rows = session.execute(
        select(Airport.iata, Airport.name).where(Airport.iata.in_(iatas))
    ).all()
    return {i: f"{n} ({i})" for i, n in rows}


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


# ---------- prijsgeschiedenis (dealscore) ----------

def record_price_point(
    session: Session,
    *,
    provider: str,
    origin: str,
    destination: str,
    nights: int,
    total_price: float,
    observed_on: datetime.date,
) -> None:
    """Leg de waargenomen retour-totaalprijs van vandaag vast (laagste per dag per route).

    Eén rij per (route, dag): bij meerdere scans op één dag houden we de **laagste** prijs.
    """
    stmt = pg_insert(DealPricePoint).values(
        provider=provider, origin=origin, destination=destination, nights=nights,
        total_price=Decimal(str(total_price)), observed_on=observed_on,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_price_points_day",
        set_={
            "total_price": func.least(DealPricePoint.total_price, stmt.excluded.total_price),
            "observed_at": func.now(),
        },
    )
    session.execute(stmt)


def price_baselines(
    session: Session,
    fingerprints,
    *,
    today: datetime.date,
    window_days: int = 90,
) -> dict[tuple[str, str, str, int], dict]:
    """Per route-fingerprint de baseline-stats over de **eerdere** dagen (excl. vandaag).

    Geeft per (provider, origin, destination, nights): mediaan, minimum, aantal waarnemingen
    en het aantal dagen historie. Eén GROUP BY-query (geen N+1). **Vandaag wordt uitgesloten**
    (``observed_on < today``) zodat een net-gescande prijs niet tegen zichzelf wordt afgezet —
    anders zou de mediaan naar de huidige prijs trekken en het aantal waarnemingen +1 zijn.
    Routes zonder eerdere historie ontbreken (de scoring valt terug op de absolute prijs).
    """
    fps = {tuple(fp) for fp in fingerprints}
    if not fps:
        return {}
    since = today - datetime.timedelta(days=window_days)
    origins = {o for _, o, _, _ in fps}
    dests = {d for _, _, d, _ in fps}
    rows = session.execute(
        select(
            DealPricePoint.provider,
            DealPricePoint.origin,
            DealPricePoint.destination,
            DealPricePoint.nights,
            func.min(DealPricePoint.total_price).label("min_total"),
            func.percentile_cont(0.5)
            .within_group(DealPricePoint.total_price.asc())
            .label("median_total"),
            func.count().label("samples"),
            func.min(DealPricePoint.observed_on).label("first_day"),
        )
        .where(
            DealPricePoint.observed_on >= since,
            DealPricePoint.observed_on < today,
            DealPricePoint.origin.in_(origins),
            DealPricePoint.destination.in_(dests),
        )
        .group_by(
            DealPricePoint.provider,
            DealPricePoint.origin,
            DealPricePoint.destination,
            DealPricePoint.nights,
        )
    ).all()
    out: dict[tuple[str, str, str, int], dict] = {}
    for r in rows:
        key = (r.provider, r.origin, r.destination, r.nights)
        if key in fps:
            out[key] = {
                "min_total": float(r.min_total),
                "median_total": float(r.median_total),
                "samples": int(r.samples),
                "days_span": (today - r.first_day).days,
            }
    return out


def airport_display(session: Session, iatas) -> dict[str, dict]:
    """IATA → {city, country} voor leesbare alerts (stad valt terug op luchthavennaam)."""
    iatas = list(iatas)
    if not iatas:
        return {}
    rows = session.execute(
        select(Airport.iata, Airport.city, Airport.name, Airport.country_code)
        .where(Airport.iata.in_(iatas))
    ).all()
    return {i: {"city": (c or n), "country": cc} for i, c, n, cc in rows}
