"""Kanaal-laag: registry + rendering + stubs. Geen netwerk."""
from __future__ import annotations

import datetime

from app.channels import email as email_mod
from app.channels.base import AlertItem, Notifier, get_notifier, registered_channels
from app.channels.telegram import format_alerts
from app.core.combine import ReturnDeal

D1 = datetime.date(2026, 8, 1)
D2 = datetime.date(2026, 8, 4)


def _deal(total, dest="BCN", nights=3):
    return ReturnDeal("ryanair", "EIN", dest, nights, total, D1, D2, total / 2, total / 2)


def test_all_channels_registered_and_conform():
    assert {"telegram", "email", "whatsapp"} <= set(registered_channels())
    for channel_type in ("telegram", "email", "whatsapp"):
        assert isinstance(get_notifier(channel_type), Notifier)


def test_telegram_formatting():
    text = format_alerts([
        AlertItem(_deal(30.0), previous_price=40.0),
        AlertItem(_deal(20.0, dest="AGP")),
    ])
    assert "€30.00" in text
    assert "was €40.00" in text
    assert "EIN ⇄ BCN" in text
    assert "━━━ 3 dagen ━━━" in text


def test_whatsapp_is_stub():
    assert get_notifier("whatsapp").send("+31600000000", [AlertItem(_deal(30.0))]) is False


def test_email_without_apikey_returns_false(monkeypatch):
    monkeypatch.setattr(email_mod.settings, "resend_api_key", "")
    assert get_notifier("email").send("reiziger@example.nl", [AlertItem(_deal(30.0))]) is False
