"""Dispatcher: alleen actieve/geverifieerde kanalen, per-kanaal dedup, en sent_alerts
pas NA een bevestigde verzending (mislukte send mag niet stil deduppen).
"""
from __future__ import annotations

import datetime

import app.dispatch as dispatch
from app.channels.base import AlertItem
from app.core import dedup
from app.core.combine import ReturnDeal
from app.db.models import Channel

D1 = datetime.date(2026, 8, 1)
D2 = datetime.date(2026, 8, 4)
OPT_IN = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)


def _deal(total=30.0, dest="BCN"):
    return ReturnDeal("ryanair", "EIN", dest, 3, total, D1, D2, total / 2, total / 2)


class _FakeNotifier:
    channel_type = "telegram"

    def __init__(self, ok=True):
        self.ok = ok
        self.calls: list = []

    def send(self, address, items: list[AlertItem]) -> bool:
        self.calls.append((address, list(items)))
        return self.ok


def _add_channel(db, user, *, verified=True, opted_in=True, enabled=True, ctype="telegram"):
    user.channels.append(
        Channel(
            type=ctype, address="999", verified=verified,
            opted_in_at=OPT_IN if opted_in else None, enabled=enabled,
        )
    )
    db.flush()


def test_sends_then_dedups(db, make_user, monkeypatch):
    user = make_user(origins=["EIN"])
    _add_channel(db, user)
    fake = _FakeNotifier(ok=True)
    monkeypatch.setattr(dispatch, "get_notifier", lambda ct: fake if ct == "telegram" else None)

    deal = _deal()
    assert dispatch.notify_user(db, user, [deal]) == 1
    assert len(fake.calls) == 1
    assert dedup.get_prev_alert(db, user.id, "telegram", deal) is not None

    # Tweede run met dezelfde deal: dedup → niets verstuurd.
    fake.calls.clear()
    assert dispatch.notify_user(db, user, [deal]) == 0
    assert fake.calls == []


def test_failed_send_does_not_record(db, make_user, monkeypatch):
    user = make_user(origins=["EIN"])
    _add_channel(db, user)
    fake = _FakeNotifier(ok=False)
    monkeypatch.setattr(dispatch, "get_notifier", lambda ct: fake)

    deal = _deal()
    assert dispatch.notify_user(db, user, [deal]) == 0
    # Mislukte send mag NIET deduppen: volgende keer opnieuw proberen.
    assert dedup.get_prev_alert(db, user.id, "telegram", deal) is None


def test_skips_unverified_channel(db, make_user, monkeypatch):
    user = make_user(origins=["EIN"])
    _add_channel(db, user, verified=False)
    fake = _FakeNotifier(ok=True)
    monkeypatch.setattr(dispatch, "get_notifier", lambda ct: fake)

    assert dispatch.notify_user(db, user, [_deal()]) == 0
    assert fake.calls == []


def test_skips_when_not_opted_in(db, make_user, monkeypatch):
    user = make_user(origins=["EIN"])
    _add_channel(db, user, opted_in=False)
    fake = _FakeNotifier(ok=True)
    monkeypatch.setattr(dispatch, "get_notifier", lambda ct: fake)

    assert dispatch.notify_user(db, user, [_deal()]) == 0
    assert fake.calls == []
