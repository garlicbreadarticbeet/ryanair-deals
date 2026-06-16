"""De can_use-naad (Fase 2-gating). Fase 1: premium mag alles, free mag alles wat
niet expliciet premium-only is (deny-set nu leeg).
"""
from __future__ import annotations

from types import SimpleNamespace

import app.core.gating as gating
from app.core.gating import can_use


def test_free_user_allowed_in_fase1():
    free = SimpleNamespace(tier="free")
    assert can_use(free, "channel:telegram")
    assert can_use(free, "channel:email")
    assert can_use(free, "mode:digest")


def test_premium_always_allowed():
    assert can_use(SimpleNamespace(tier="premium"), "wat-dan-ook")


def test_premium_only_denylist_blocks_free(monkeypatch):
    monkeypatch.setattr(gating, "PREMIUM_ONLY_FEATURES", frozenset({"mode:instant"}))
    assert can_use(SimpleNamespace(tier="free"), "mode:instant") is False
    assert can_use(SimpleNamespace(tier="premium"), "mode:instant") is True
