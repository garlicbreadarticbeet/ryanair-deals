"""De ENIGE plek met free/premium-logica: can_use(user, feature) + limieten.

De premium-feature-namen komen uit settings/env (settings.premium_only_feature_set), niet
hardgecodeerd hier — zo blijft core/ vrij van kanaal-/maatschappijnamen (purity-test). Match
en scan blijven gating-vrij; alleen notify, de worker (instant vs digest) en de web/bot-laag
(voorkeurslimieten) vragen hier toestemming.
"""
from __future__ import annotations

from typing import Protocol

from app.settings import settings

_PREMIUM_MANY = 10_000  # praktisch "onbeperkt" voor premium


class _User(Protocol):
    tier: str


def _is_premium(user) -> bool:
    return getattr(user, "tier", "free") == "premium"


def can_use(user, feature: str) -> bool:
    """Premium mag alles; free mag alles behalve de premium-only features (uit settings)."""
    if _is_premium(user):
        return True
    return feature not in settings.premium_only_feature_set


def max_origins(user) -> int:
    """Maximum aantal vertrekvelden: premium ~onbeperkt, free settings.free_max_origins."""
    return _PREMIUM_MANY if _is_premium(user) else settings.free_max_origins


def effective_alert_mode(user) -> str:
    """De werkelijke alert-modus: 'instant' alleen als de gebruiker het koos én mag; anders 'digest'."""
    chosen = getattr(getattr(user, "preferences", None), "alert_mode", "digest")
    if chosen == "instant" and can_use(user, "mode:instant"):
        return "instant"
    return "digest"
