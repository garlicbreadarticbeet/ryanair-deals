"""Provider-agnostisch contract: de BillingProvider-interface + een provider-registry.

Een nieuwe betaalprovider = één nieuw bestand hier met een @register_billing_provider-klasse
die ``create_checkout`` en ``cancel`` implementeert. Webhookverwerking is per provider een eigen
functie in app/billing.py (verschillende payloads), maar de tier-flip loopt daar via één plek.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session

from app.db.models import User


@runtime_checkable
class BillingProvider(Protocol):
    """Interface die elke betaalprovider implementeert."""

    name: str  # 'lemonsqueezy' / 'mollie'

    def create_checkout(self, session: Session, user: User, plan: str) -> str:
        """Start een checkout voor ``plan`` ('monthly'/'annual'); geef de checkout-URL terug."""
        ...

    def cancel(self, session: Session, user: User) -> None:
        """Zeg het abonnement op bij de provider en schaal de gebruiker terug naar gratis."""
        ...


_REGISTRY: dict[str, BillingProvider] = {}


def register_billing_provider(cls: type) -> type:
    """Decorator: registreer een (stateless) BillingProvider-instantie onder zijn naam."""
    _REGISTRY[cls.name] = cls()
    return cls


def get_billing_provider(name: str) -> BillingProvider | None:
    """De geregistreerde provider voor deze naam, of None."""
    return _REGISTRY.get(name)


def registered_billing_providers() -> list[str]:
    return sorted(_REGISTRY)


# Trigger registratie van de gebundelde providers (onderaan i.v.m. circulaire import).
from app.billing_providers import lemonsqueezy_provider, mollie_provider  # noqa: E402,F401
