"""Kanaal-agnostisch contract: de Notifier-interface + een kanaal-registry.

Een nieuw kanaal = één nieuw bestand hier met een @register_notifier-klasse. De dispatcher
(app/dispatch.py) en core/ kennen geen concreet kanaal; selectie gaat via deze registry.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.core.combine import ReturnDeal


@dataclass(frozen=True)
class AlertItem:
    """Eén te melden deal + (optioneel) de vorige gemelde prijs voor "was €X"."""

    deal: ReturnDeal
    previous_price: float | None = None


@runtime_checkable
class Notifier(Protocol):
    """Interface die elk bezorgkanaal implementeert."""

    channel_type: str  # 'telegram' / 'email' / 'whatsapp'

    def send(self, address: str, items: list[AlertItem]) -> bool:
        """Verstuur de alerts naar één adres; True bij bevestigde verzending."""
        ...


_REGISTRY: dict[str, Notifier] = {}


def register_notifier(cls: type) -> type:
    """Decorator: registreer een (stateless) Notifier-instantie onder zijn channel_type."""
    _REGISTRY[cls.channel_type] = cls()
    return cls


def get_notifier(channel_type: str) -> Notifier | None:
    """De geregistreerde Notifier voor dit kanaaltype, of None."""
    return _REGISTRY.get(channel_type)


def registered_channels() -> list[str]:
    return sorted(_REGISTRY)


# Trigger registratie van de gebundelde kanalen (onderaan i.v.m. circulaire import).
from app.channels import email, telegram, whatsapp  # noqa: E402,F401
