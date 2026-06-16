"""Retour-combinatie — provider-onafhankelijke port van deals.best_returns().

Werkt UITSLUITEND op genormaliseerde DailyFare-lijsten; importeert geen enkele adapter
of maatschappij-specifiek type. Voor elke reisduur N wordt de goedkoopste combinatie
gezocht: vertrek op dag D + terug op dag D+N; laagste totaal per (route, N) wint.

Bewust gelijk aan het bewezen origineel:
- rekenen in float met ``round(p_out + p_in, 2)`` en strikte ``<``-vergelijking, zodat
  de no-regression-test (combine == deals.best_returns) byte-voor-byte slaagt; de DB-laag
  converteert pas bij het persisteren naar NUMERIC(8,2);
- horizoncheck op de HEENreis (d_out), net als vroeger;
- ``trip_lengths``/``today``/``horizon_end`` zijn nu argumenten (de unie over alle
  gebruikers) i.p.v. config-reads.

TODO(mixed-carrier): heen en terug komen van DEZELFDE provider én route. Gemengde
carriers (heen via maatschappij A, terug via maatschappij B) vereisen cross-provider
matching op (origin, destination, datum) + een extra provider-dimensie in de fingerprint;
bewust uit scope in Fase 1.
"""
from __future__ import annotations

import datetime
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.providers.base import DailyFare


@dataclass(frozen=True)
class ReturnDeal:
    """Goedkoopste retour voor één (provider, route, reisduur) — output van combine."""

    provider: str
    origin: str
    destination: str
    nights: int
    total: float
    out_date: datetime.date
    in_date: datetime.date
    out_price: float
    in_price: float
    out_departure: str | None = None
    in_departure: str | None = None


def deal_row_to_return_deal(row) -> ReturnDeal:
    """Zet een opgeslagen deal-rij (duck-typed, met .total_price etc.) om naar ReturnDeal.

    Gedeeld door de worker (digest) en de bot (/deals) zodat match op DB-deals dezelfde
    weg loopt als op verse scan-resultaten. Geen import van het DB-model nodig.
    """
    return ReturnDeal(
        provider=row.provider, origin=row.origin, destination=row.destination,
        nights=row.nights, total=float(row.total_price),
        out_date=row.out_date, in_date=row.in_date,
        out_price=float(row.out_price), in_price=float(row.in_price),
    )


def best_returns(
    outbound: Iterable[DailyFare],
    inbound: Iterable[DailyFare],
    trip_lengths: Sequence[int],
    today: datetime.date,
    horizon_end: datetime.date,
) -> list[ReturnDeal]:
    """Voor elke reisduur de goedkoopste heen+terug-combinatie.

    Eén DailyFare per dag verwacht; bij duplicaten wint de laatst-geziene (dict-semantiek,
    identiek aan de oude fetch_perday-dict).
    """
    out_by_date = {f.fly_date: f for f in outbound}
    in_by_date = {f.fly_date: f for f in inbound}

    deals: list[ReturnDeal] = []
    for n in trip_lengths:
        best: ReturnDeal | None = None
        for d_out, fo in out_by_date.items():
            if d_out < today or d_out > horizon_end:
                continue
            fi = in_by_date.get(d_out + datetime.timedelta(days=n))
            if fi is None:
                continue
            total = round(fo.price + fi.price, 2)
            if best is None or total < best.total:
                best = ReturnDeal(
                    provider=fo.provider,
                    origin=fo.origin,
                    destination=fo.destination,
                    nights=n,
                    total=total,
                    out_date=d_out,
                    in_date=fi.fly_date,
                    out_price=fo.price,
                    in_price=fi.price,
                    out_departure=fo.departure,
                    in_departure=fi.departure,
                )
        if best is not None:
            deals.append(best)
    return deals
