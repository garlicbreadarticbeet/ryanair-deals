"""De worker-lus: instant (premium, per run) vs digest (gratis, dagelijks), met gedeelde dedup.
Met nep-provider en nep-notifier (geen netwerk).
"""
from __future__ import annotations

import datetime

import app.core.scan as scan_mod
import app.dispatch as dispatch_mod
from app.channels.base import AlertItem
from app.db.models import Channel
from app.providers.base import DailyFare, Route
from app.worker import run_digest, run_once

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


def _telegram(db, user):
    user.channels.append(
        Channel(type="telegram", address="900", verified=True, opted_in_at=OPT_IN, enabled=True)
    )
    db.flush()


def _patch(monkeypatch, notifier):
    monkeypatch.setattr(scan_mod, "get_provider", lambda code: _FakeProvider())
    monkeypatch.setattr(dispatch_mod, "get_notifier", lambda ct: notifier if ct == "telegram" else None)


def test_instant_premium_user_alerted_by_run_once(db, make_user, monkeypatch):
    user = make_user(origins=["EIN"], threshold=50, tier="premium", alert_mode="instant")
    _telegram(db, user)
    notifier = _FakeNotifier()
    _patch(monkeypatch, notifier)

    stats = run_once(db, today=TODAY)
    assert stats["mode"] == "instant"
    assert stats["alerts"] == 1
    assert notifier.calls[0][1][0].deal.total == 35.0

    # Tweede run: dedup → niets nieuws.
    notifier.calls.clear()
    assert run_once(db, today=TODAY)["alerts"] == 0
    assert notifier.calls == []


def test_digest_user_skipped_by_run_once_then_alerted_by_digest(db, make_user, monkeypatch):
    user = make_user(origins=["EIN"], threshold=50, tier="free", alert_mode="digest")
    _telegram(db, user)
    notifier = _FakeNotifier()
    _patch(monkeypatch, notifier)

    # run_once scant (vult deals-tabel) maar meldt de digest-gebruiker NIET.
    once = run_once(db, today=TODAY)
    assert once["deals"] >= 1
    assert once["alerts"] == 0
    assert notifier.calls == []

    # De dagelijkse digest meldt 'm wél, uit de gepersisteerde deals.
    digest = run_digest(db)
    assert digest["mode"] == "digest"
    assert digest["alerts"] == 1
    assert notifier.calls[0][1][0].deal.total == 35.0
