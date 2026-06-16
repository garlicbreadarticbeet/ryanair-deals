"""De worker-lus: één scan → per user match → notify, en dedup over runs heen.
Met nep-provider en nep-notifier (geen netwerk).
"""
from __future__ import annotations

import datetime

import app.core.scan as scan_mod
import app.dispatch as dispatch_mod
from app.channels.base import AlertItem
from app.db.models import Channel
from app.providers.base import DailyFare, Route
from app.web import auth  # noqa: F401  (zorgt dat app.web importeerbaar is)
from app.worker import run_once

TODAY = datetime.date(2026, 6, 16)
OUT = TODAY + datetime.timedelta(days=10)
IN3 = OUT + datetime.timedelta(days=3)
OPT_IN = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)


class _FakeProvider:
    code = "ryanair"

    def discover_routes(self, origins, date_from, date_to, destination_country=None):
        return [Route("ryanair", "EIN", "BCN")] if "EIN" in origins else []

    def daily_fares(self, origin, destination, months, currency):
        if (origin, destination) == ("EIN", "BCN"):
            return [DailyFare("ryanair", "EIN", "BCN", OUT, 20.0, currency)]
        if (origin, destination) == ("BCN", "EIN"):
            return [DailyFare("ryanair", "BCN", "EIN", IN3, 15.0, currency)]
        return []


class _FakeNotifier:
    channel_type = "telegram"

    def __init__(self):
        self.calls: list = []

    def send(self, address, items: list[AlertItem]) -> bool:
        self.calls.append((address, list(items)))
        return True


def test_worker_scans_matches_notifies_and_dedups(db, make_user, monkeypatch):
    user = make_user(origins=["EIN"], threshold=50)
    user.channels.append(
        Channel(type="telegram", address="900", verified=True, opted_in_at=OPT_IN, enabled=True)
    )
    db.flush()

    fake_notifier = _FakeNotifier()
    monkeypatch.setattr(scan_mod, "get_provider", lambda code: _FakeProvider())
    monkeypatch.setattr(
        dispatch_mod, "get_notifier", lambda ct: fake_notifier if ct == "telegram" else None
    )

    stats = run_once(db, today=TODAY)
    assert stats["deals"] >= 1
    assert stats["alerts"] == 1
    assert len(fake_notifier.calls) == 1
    address, items = fake_notifier.calls[0]
    assert address == "900"
    assert items[0].deal.total == 35.0

    # Tweede run: zelfde deal → per-kanaal dedup → geen nieuwe alert.
    fake_notifier.calls.clear()
    stats2 = run_once(db, today=TODAY)
    assert stats2["alerts"] == 0
    assert fake_notifier.calls == []
