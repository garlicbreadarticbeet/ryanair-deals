"""run_scan() orkestreert provider → combine → upsert deals, en geeft de verse deals terug.
Met een nep-provider (geen netwerk), via dezelfde registry-seam die productie gebruikt.
"""
from __future__ import annotations

import datetime

from sqlalchemy import select

from app.core.scan import run_scan
from app.db.models import Deal
from app.providers.base import DailyFare, Route

TODAY = datetime.date(2026, 6, 16)
OUT_DAY = TODAY + datetime.timedelta(days=10)
IN_DAY = OUT_DAY + datetime.timedelta(days=3)


class _FakeProvider:
    code = "ryanair"

    def discover_routes(self, origins, date_from, date_to, destination_country=None):
        assert "EIN" in origins
        return [Route("ryanair", "EIN", "BCN")]

    def daily_fares(self, origin, destination, months, currency):
        if (origin, destination) == ("EIN", "BCN"):
            return [DailyFare("ryanair", "EIN", "BCN", OUT_DAY, 20.0, currency)]
        if (origin, destination) == ("BCN", "EIN"):
            return [DailyFare("ryanair", "BCN", "EIN", IN_DAY, 15.0, currency)]
        return []


def test_run_scan_finds_and_persists_deal(db, make_user, monkeypatch):
    make_user(origins=["EIN"], trip_lengths=[3, 5, 7])
    monkeypatch.setattr("app.core.scan.get_provider", lambda code: _FakeProvider())

    deals = run_scan(db, today=TODAY)

    # 3-nachten retour EIN⇄BCN voor 20 + 15 = 35
    combo = [d for d in deals if d.nights == 3 and d.destination == "BCN"]
    assert len(combo) == 1
    assert combo[0].total == 35.0
    assert combo[0].out_date == OUT_DAY and combo[0].in_date == IN_DAY

    row = db.execute(
        select(Deal).where(Deal.origin == "EIN", Deal.destination == "BCN", Deal.nights == 3)
    ).scalar_one()
    assert float(row.total_price) == 35.0
    assert row.currency == "EUR"


def test_run_scan_empty_when_no_users(db, monkeypatch):
    # Geen gebruikers/origins → geen scan-doelen → lege uitkomst, geen provideraanroep.
    monkeypatch.setattr(
        "app.core.scan.get_provider",
        lambda code: (_ for _ in ()).throw(AssertionError("provider mag niet aangeroepen worden")),
    )
    assert run_scan(db, today=TODAY) == []
