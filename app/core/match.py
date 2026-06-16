"""Per-gebruiker matching: filtert de gevonden deals op de voorkeuren van één gebruiker.

Provider-agnostisch en netwerkloos: werkt op ReturnDeal-objecten (vers uit de scan) en de
voorkeuren uit de DB. Hier landen de oude config-filters (ORIGINS/ONLY/EXCLUDE/
DESTINATION_COUNTRY/THRESHOLD), maar nu per gebruiker. De per-kanaal dedup gebeurt in notify.
"""
from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.core.combine import ReturnDeal
from app.db import repo
from app.db.models import User


def match_user(session: Session, user: User, deals: Iterable[ReturnDeal]) -> list[ReturnDeal]:
    """De deals die voldoen aan de voorkeuren van ``user`` (drempel, origins, reisduren, filter).

    Twee gebruikers met verschillende voorkeuren krijgen aantoonbaar verschillende resultaten
    op dezelfde invoer (acceptatiecriterium 4).
    """
    prefs = user.preferences
    if prefs is None:
        return []

    deals = list(deals)
    allowed = repo.allowed_provider_origins(session, user.id)
    trip_lengths = set(prefs.trip_lengths or [])
    threshold = float(prefs.threshold)
    mode = prefs.dest_filter_mode
    whitelist = set(prefs.dest_whitelist or [])
    blacklist = set(prefs.dest_blacklist or [])
    countries = set(prefs.dest_countries or [])

    dest_country: dict[str, str] = {}
    if mode == "country":
        dest_country = repo.destination_countries(session, {d.destination for d in deals})

    result: list[ReturnDeal] = []
    for d in deals:
        if (d.provider, d.origin) not in allowed:
            continue
        if d.nights not in trip_lengths:
            continue
        if d.total > threshold:
            continue
        if mode == "whitelist" and d.destination not in whitelist:
            continue
        if mode == "blacklist" and d.destination in blacklist:
            continue
        if mode == "country" and dest_country.get(d.destination) not in countries:
            continue
        result.append(d)
    return result
