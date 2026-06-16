"""Gedeelde test-fixtures.

De ``db``-fixture geeft een sessie in een transactie die na elke test wordt teruggedraaid
(geen vervuiling). Vereist een bereikbare Postgres op DATABASE_URL met de migraties gedraaid;
is die er niet (bv. CI zonder DB), dan worden DB-tests netjes geskipt — de pure tests
(combine-pariteit e.d.) blijven gewoon draaien.
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import Preference, Provider, User, UserOrigin
from app.db.session import engine, session_scope


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


DB_AVAILABLE = _db_available()


@pytest.fixture(scope="session")
def _seeded():
    """Zorg eenmalig dat providers/airports bestaan (idempotent, gecommit)."""
    if DB_AVAILABLE:
        from app.db.seed_airports import seed_all

        with session_scope() as session:
            seed_all(session)
    yield


@pytest.fixture
def db(_seeded) -> Session:
    """Transactionele sessie; rollt terug na de test."""
    if not DB_AVAILABLE:
        pytest.skip("geen database bereikbaar op DATABASE_URL")
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()


@pytest.fixture
def make_user(db):
    """Factory: maak een actieve gebruiker met voorkeuren + gekozen origins (ryanair)."""
    ryanair_id = db.execute(select(Provider.id).where(Provider.code == "ryanair")).scalar_one()

    def _make(
        origins=("EIN",),
        threshold=50,
        trip_lengths=(3, 5, 7),
        mode="all",
        dest_whitelist=(),
        dest_blacklist=(),
        dest_countries=(),
        tier="free",
    ) -> User:
        user = User(status="active", tier=tier)
        db.add(user)
        db.flush()
        db.add(
            Preference(
                user_id=user.id,
                threshold=Decimal(str(threshold)),
                trip_lengths=list(trip_lengths),
                dest_filter_mode=mode,
                dest_whitelist=list(dest_whitelist),
                dest_blacklist=list(dest_blacklist),
                dest_countries=list(dest_countries),
            )
        )
        for iata in origins:
            db.add(UserOrigin(user_id=user.id, provider_id=ryanair_id, origin_iata=iata))
        db.flush()
        return user

    return _make
