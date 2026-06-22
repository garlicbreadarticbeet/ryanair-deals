"""Scan-orkestratie — provider-agnostisch, draait op GLOBALE aggregaten.

Schaalt met het aantal unieke (provider, origin)-paren, niet met het aantal gebruikers:
de unie komt uit één SELECT DISTINCT (repo.deduped_origin_targets). Vult/ververst de
deals-tabel en retourneert de verse ReturnDeals zodat match direct kan draaien.

Eén scan i.p.v. één per gebruiker: dezelfde route wordt maar één keer bij de provider opgehaald.
"""
from __future__ import annotations

import dataclasses
import datetime
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session

from app.core.combine import ReturnDeal, best_returns
from app.core.horizon import months_in_horizon
from app.db import repo
from app.providers.registry import get_provider
from app.settings import settings


def run_scan(session: Session, today: datetime.date | None = None) -> list[ReturnDeal]:
    """Scan alle door gebruikers gekozen (provider, origin)-paren en upsert de deals.

    Retourneert de gevonden ReturnDeals (vers, voor directe match). Fase 1 is EUR-only.
    """
    today = today or datetime.date.today()
    targets = repo.deduped_origin_targets(session)
    if not targets:
        return []

    months_ahead = repo.max_months_ahead(session) or settings.default_months_ahead
    trip_lengths = repo.union_trip_lengths(session) or settings.default_trip_length_list
    horizon_end = today + datetime.timedelta(days=int(months_ahead * 30.5))
    months = months_in_horizon(months_ahead, trip_lengths, today)

    # Groepeer de origins per provider (één adapter-instantie per provider).
    by_provider: dict[str, list[str]] = {}
    for code, iata in targets:
        by_provider.setdefault(code, []).append(iata)

    all_deals: list[ReturnDeal] = []
    for code, origins in by_provider.items():
        provider = get_provider(code)

        # Retour-native pad: bronnen die de retour al gecombineerd leveren (ReturnFareProvider).
        # Geen discover_routes/combine nodig; de bron geeft direct ReturnFares.
        if hasattr(provider, "return_deals"):
            for rf in provider.return_deals(origins, today, horizon_end, trip_lengths, settings.currency):
                deal = _returnfare_to_deal(rf)
                _persist(session, deal, today)
                all_deals.append(deal)
            continue

        # DailyFare-pad: ontdek routes, haal heen+terug op, combineer tot retours.
        routes = list(provider.discover_routes(origins, today, horizon_end))

        def _fetch(route) -> list[ReturnDeal]:
            outbound = list(provider.daily_fares(route.origin, route.destination, months, settings.currency))
            inbound = list(provider.daily_fares(route.destination, route.origin, months, settings.currency))
            return best_returns(outbound, inbound, trip_lengths, today, horizon_end)

        # Parallel ophalen (politeness: dezelfde CONCURRENCY-cap als vroeger). De DB-upsert
        # gebeurt in de hoofdthread, want de SQLAlchemy-sessie is niet thread-safe.
        with ThreadPoolExecutor(max_workers=settings.concurrency) as pool:
            for deals in pool.map(_fetch, routes):
                for d in deals:
                    d = _with_booking(provider, d)
                    _persist(session, d, today)
                    all_deals.append(d)
    return all_deals


def _with_booking(provider, d: ReturnDeal) -> ReturnDeal:
    """Verrijk een DailyFare-pad-deal met de boekingslink + airline-naam van de provider.

    Duck-typed en provider-agnostisch (geen maatschappijnaam hier): een provider die deze
    capability biedt, levert ``booking_url(origin, dest, out_date, in_date)`` en/of
    ``airline_name``. Bronnen die het niet bieden laten de deal ongemoeid.
    """
    url = None
    builder = getattr(provider, "booking_url", None)
    if callable(builder):
        try:
            url = builder(d.origin, d.destination, d.out_date, d.in_date)
        except Exception:  # noqa: BLE001 — een kapotte link mag de scan niet stoppen
            url = None
    airline = getattr(provider, "airline_name", None)
    if url or airline:
        return dataclasses.replace(d, deeplink=url or d.deeplink, airline=airline or d.airline)
    return d


def _returnfare_to_deal(rf) -> ReturnDeal:
    """Zet een retour-native ReturnFare om naar een ReturnDeal. Gecachte retours splitsen
    niet in heen/terug; we verdelen het totaal 50/50 voor opslag (match/notify gebruiken
    alleen ``total``). Behoudt deeplink + airline voor de alert."""
    out_p = round(rf.total / 2, 2)
    return ReturnDeal(
        provider=rf.provider, origin=rf.origin, destination=rf.destination, nights=rf.nights,
        total=rf.total, out_date=rf.out_date, in_date=rf.in_date,
        out_price=out_p, in_price=round(rf.total - out_p, 2),
        deeplink=rf.deeplink, airline=rf.airline,
    )


def _persist(session: Session, d: ReturnDeal, today: datetime.date) -> None:
    """Upsert één ReturnDeal naar de deals-tabel + leg de prijswaarneming van vandaag vast."""
    repo.upsert_deal(
        session, provider=d.provider, origin=d.origin, destination=d.destination,
        nights=d.nights, out_date=d.out_date, in_date=d.in_date,
        out_price=d.out_price, in_price=d.in_price, total_price=d.total,
        currency=settings.currency, airline=d.airline, deeplink=d.deeplink,
    )
    repo.record_price_point(
        session, provider=d.provider, origin=d.origin, destination=d.destination,
        nights=d.nights, total_price=d.total, observed_on=today,
    )
