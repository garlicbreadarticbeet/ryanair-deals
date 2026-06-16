"""De ENIGE plek met free/premium-logica: can_use(user, feature).

Fase 1 heeft nog geen echte gating (geen Mollie/betalingen). Model: premium mag alles;
free mag alles wat NIET expliciet premium-only is. De deny-set is in Fase 1 leeg — Fase 2
vult 'm (bv. een instant-modus of een premium-kanaal). Zo staan er bewust geen kanaal- of
maatschappijnamen in core/: de caller (dispatcher) geeft de feature-string door.
"""
from __future__ import annotations

from typing import Protocol


class _HasTier(Protocol):
    tier: str


# Features die alleen premium mag. Leeg in Fase 1; Fase 2 vult deze deny-set
# (bv. "mode:instant" of een premium-kanaal). De caller bepaalt de feature-string.
PREMIUM_ONLY_FEATURES: frozenset[str] = frozenset()


def can_use(user: _HasTier, feature: str) -> bool:
    """Mag deze gebruiker deze feature gebruiken?

    Fase 1: premium mag alles; free mag alles behalve de (nu lege) PREMIUM_ONLY_FEATURES.
    De echte premium-businessregels komen in Fase 2 hier — zonder de rest aan te raken.
    """
    if getattr(user, "tier", "free") == "premium":
        return True
    return feature not in PREMIUM_ONLY_FEATURES
