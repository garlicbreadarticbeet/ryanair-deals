"""Per-gebruiker dedup — de DB-vervanging van de state.json-logica uit detect_new_deals.

Fingerprint = (provider, origin, destination, nights) — ZONDER datums, exact zoals de oude
state-key "ORIG-DEST-Nd". "Nieuw of goedkoper" met dezelfde float-epsilon (0.001). De
dedup is per (gebruiker, fingerprint, kanaal): hetzelfde koopje kan via verschillende
kanalen afzonderlijk worden gemeld (conform het sent_alerts-ontwerp).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import SentAlert

# Zelfde drempel-epsilon als detect_new_deals (deals.py): bescherming tegen float/round-ruis.
EPSILON = 0.001


class _DealLike(Protocol):
    provider: str
    origin: str
    destination: str
    nights: int
    total: float
    out_date: object
    in_date: object


def fingerprint(deal: _DealLike) -> tuple[str, str, str, int]:
    """De datumloze dedup-sleutel (per gebruiker + kanaal aangevuld in sent_alerts)."""
    return (deal.provider, deal.origin, deal.destination, deal.nights)


def get_prev_alert(
    session: Session, user_id: int, channel_type: str, deal: _DealLike
) -> SentAlert | None:
    """Laatst gemelde alert voor deze (gebruiker, fingerprint, kanaal), of None."""
    return session.execute(
        select(SentAlert).where(
            SentAlert.user_id == user_id,
            SentAlert.provider == deal.provider,
            SentAlert.origin == deal.origin,
            SentAlert.destination == deal.destination,
            SentAlert.nights == deal.nights,
            SentAlert.channel_type == channel_type,
        )
    ).scalar_one_or_none()


def is_new_or_cheaper(prev: SentAlert | None, price: float) -> bool:
    """True als nog nooit gemeld, of strikt goedkoper dan de laatst gemelde prijs.

    Exact de semantiek van detect_new_deals: prev is None OF price < prev_alerted - 0.001.
    (De drempelcheck price <= threshold zit in match.)
    """
    if prev is None:
        return True
    return price < float(prev.alerted_price) - EPSILON


def record_sent_alert(
    session: Session, user_id: int, channel_type: str, deal: _DealLike
) -> None:
    """Leg vast dat deze deal voor deze gebruiker+kanaal is gemeld (upsert: prijs/datums bij).

    Aanroepen NA een bevestigde verzending, zodat een mislukte send niet stil dedupt.
    """
    values = {
        "user_id": user_id,
        "provider": deal.provider,
        "origin": deal.origin,
        "destination": deal.destination,
        "nights": deal.nights,
        "channel_type": channel_type,
        "alerted_price": Decimal(str(deal.total)),
        "out_date": deal.out_date,
        "in_date": deal.in_date,
    }
    stmt = pg_insert(SentAlert).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_sent_alerts_fingerprint",
        set_={
            "alerted_price": stmt.excluded.alerted_price,
            "out_date": stmt.excluded.out_date,
            "in_date": stmt.excluded.in_date,
            "last_alerted_at": func.now(),
        },
    )
    session.execute(stmt)
