"""Verrijk gematchte deals met stadsnamen, bestemmingsland en de dealscore.

Batcht de queries (één voor de luchthavens, één voor de baselines) zodat verrijken O(1)
DB-rondjes kost i.p.v. per deal. De uitkomst wordt op de route-fingerprint
(provider, origin, destination, nights) gekoppeld — dezelfde sleutel als dedup.
"""
from __future__ import annotations

import datetime
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.combine import ReturnDeal
from app.core.scoring import DealScore, score_deal
from app.db import repo

_Fingerprint = tuple[str, str, str, int]


@dataclass(frozen=True)
class Enrichment:
    city_from: str
    city_to: str
    country_to: str | None
    score: DealScore


def _fingerprint(d: ReturnDeal) -> _Fingerprint:
    return (d.provider, d.origin, d.destination, d.nights)


def enrich_deals(
    session: Session,
    deals: Iterable[ReturnDeal],
    *,
    today: datetime.date | None = None,
) -> dict[_Fingerprint, Enrichment]:
    """Map route-fingerprint → Enrichment (stad heen/terug, bestemmingsland, dealscore)."""
    deals = list(deals)
    if not deals:
        return {}
    today = today or datetime.date.today()
    iatas = {d.origin for d in deals} | {d.destination for d in deals}
    display = repo.airport_display(session, iatas)
    fps = {_fingerprint(d) for d in deals}
    baselines = repo.price_baselines(session, fps, today=today)

    out: dict[_Fingerprint, Enrichment] = {}
    for d in deals:
        fp = _fingerprint(d)
        dst = display.get(d.destination, {})
        out[fp] = Enrichment(
            city_from=display.get(d.origin, {}).get("city", d.origin),
            city_to=dst.get("city", d.destination),
            country_to=dst.get("country"),
            score=score_deal(d.total, baselines.get(fp)),
        )
    return out
