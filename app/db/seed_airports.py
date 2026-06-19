"""Idempotente seed van de centrale luchthavenlijst + providers.

Bron: app/db/data/airports.json — een gebundelde momentopname van Ryanair's publieke
airports-endpoint (IATA, naam, land-alpha2, stad). Geen netwerk nodig bij het seeden;
verversen kan met scripts/refresh_airports.py.

De vijf NL/grensvelden uit de oude config.ORIGINS staan als is_origin_seed=true
(default-suggestie in de UI); Maastricht/Groningen zijn toegevoegd hoewel Ryanair
daar niet vliegt, want vertrekvelden zijn gebruiker-selecteerbaar (regel 4).

Draaien:  python -m app.db.seed_airports
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import Airport, Provider
from app.db.session import session_scope

_AIRPORTS_FILE = Path(__file__).resolve().parent / "data" / "airports.json"

# Providers die het systeem kent. Een nieuwe maatschappij = rij hier + adapter.
_PROVIDERS = [
    {"code": "travelpayouts", "display_name": "Travelpayouts (Aviasales)", "enabled": True},
    {"code": "ryanair", "display_name": "Ryanair", "enabled": True},
    {"code": "wizzair", "display_name": "Wizz Air", "enabled": False},  # stub tot Fase 2
]


def _load_airports() -> list[dict]:
    """Lees de gebundelde luchthavenlijst."""
    return json.loads(_AIRPORTS_FILE.read_text(encoding="utf-8"))


def seed_providers(session: Session) -> int:
    """Upsert de providers (DO NOTHING zodat een runtime enabled-toggle blijft staan)."""
    stmt = pg_insert(Provider).values(_PROVIDERS).on_conflict_do_nothing(index_elements=["code"])
    session.execute(stmt)
    return len(_PROVIDERS)


def seed_airports(session: Session) -> int:
    """Upsert alle luchthavens (DO UPDATE houdt naam/land/stad/seed-vlag actueel)."""
    rows = _load_airports()
    stmt = pg_insert(Airport).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["iata"],
        set_={
            "name": stmt.excluded.name,
            "country_code": stmt.excluded.country_code,
            "city": stmt.excluded.city,
            "is_origin_seed": stmt.excluded.is_origin_seed,
        },
    )
    session.execute(stmt)
    return len(rows)


def seed_all(session: Session) -> tuple[int, int]:
    """Seed providers + luchthavens binnen één transactie."""
    n_prov = seed_providers(session)
    n_air = seed_airports(session)
    return n_prov, n_air


def main() -> None:
    with session_scope() as session:
        n_prov, n_air = seed_all(session)
    print(f"Seed klaar: {n_prov} providers, {n_air} luchthavens.")


if __name__ == "__main__":
    main()
