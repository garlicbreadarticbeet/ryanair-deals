"""WhatsApp-notifier: no-op tot de flag aan staat; correcte Cloud-API-payload als hij aan is."""
from __future__ import annotations

import datetime

import app.channels.whatsapp as wa
from app.channels.base import AlertItem
from app.core.combine import ReturnDeal
from app.settings import settings

D1 = datetime.date(2026, 8, 1)
D2 = datetime.date(2026, 8, 4)


def _item(total=30.0):
    return AlertItem(ReturnDeal("ryanair", "EIN", "BCN", 3, total, D1, D2, total / 2, total / 2))


def test_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_enabled", False)
    assert wa.WhatsAppNotifier().send("+31600000000", [_item()]) is False


def test_noop_when_enabled_but_no_credentials(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_enabled", True)
    monkeypatch.setattr(settings, "whatsapp_token", "")
    monkeypatch.setattr(settings, "whatsapp_phone_id", "")
    assert wa.WhatsAppNotifier().send("+31600000000", [_item()]) is False


def test_sends_when_enabled_with_credentials(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_enabled", True)
    monkeypatch.setattr(settings, "whatsapp_token", "tok")
    monkeypatch.setattr(settings, "whatsapp_phone_id", "123")
    captured = {}

    class _Resp:
        status_code = 200

    class _Session:
        def post(self, url, headers=None, json=None, timeout=None):
            captured.update(url=url, headers=headers, json=json)
            return _Resp()

    monkeypatch.setattr(wa, "get_session", lambda: _Session())

    ok = wa.WhatsAppNotifier().send("+31600000000", [_item(29.99)])
    assert ok is True
    assert captured["url"].endswith("/123/messages")
    assert captured["headers"]["Authorization"] == "Bearer tok"
    assert captured["json"]["messaging_product"] == "whatsapp"
    assert captured["json"]["to"] == "+31600000000"
    assert "29.99" in captured["json"]["text"]["body"]
