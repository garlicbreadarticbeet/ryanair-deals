"""De can_use-naad + gratis-limieten (Fase 2). Premium-features komen uit settings/env."""
from __future__ import annotations

from types import SimpleNamespace

from app.core.gating import can_use, effective_alert_mode, max_origins
from app.settings import settings


def _user(tier="free", alert_mode="instant"):
    return SimpleNamespace(tier=tier, preferences=SimpleNamespace(alert_mode=alert_mode))


def test_free_blocked_from_premium_features():
    free = _user("free")
    # Gratis mag de basis:
    assert can_use(free, "channel:telegram")
    assert can_use(free, "channel:email")
    assert can_use(free, "mode:digest")
    # ...maar niet de premium-only features (default settings):
    assert can_use(free, "mode:instant") is False
    assert can_use(free, "channel:whatsapp") is False


def test_premium_can_use_everything():
    prem = _user("premium")
    assert can_use(prem, "mode:instant")
    assert can_use(prem, "channel:whatsapp")
    assert can_use(prem, "wat-dan-ook")


def test_max_origins_per_tier():
    assert max_origins(_user("free")) == settings.free_max_origins
    assert max_origins(_user("premium")) > settings.free_max_origins


def test_effective_alert_mode():
    assert effective_alert_mode(_user("free", "instant")) == "digest"   # mag geen instant
    assert effective_alert_mode(_user("free", "digest")) == "digest"
    assert effective_alert_mode(_user("premium", "instant")) == "instant"
    assert effective_alert_mode(_user("premium", "digest")) == "digest"


def test_premium_only_set_is_settings_driven(monkeypatch):
    monkeypatch.setattr(settings, "premium_only_features", "mode:instant")
    free = _user("free")
    assert can_use(free, "channel:whatsapp") is True   # niet meer premium-only
    assert can_use(free, "mode:instant") is False
