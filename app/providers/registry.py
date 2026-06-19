"""Provider-registry: providercode -> adapterklasse.

Een nieuwe maatschappij registreert zichzelf met de @register-decorator; ``active_providers``
instantieert alleen de codes die in de DB op enabled staan (zie settings/providers-tabel).
De registry is de enige plek die alle adapters kent — combine/match/notify niet.
"""
from __future__ import annotations

from collections.abc import Iterable

from app.providers.base import FlightProvider

_REGISTRY: dict[str, type] = {}


def register(cls: type) -> type:
    """Decorator: registreer een adapterklasse onder zijn ``code``."""
    _REGISTRY[cls.code] = cls
    return cls


def get_provider(code: str) -> FlightProvider:
    """Instantieer één adapter op code (KeyError als onbekend)."""
    return _REGISTRY[code]()


def registered_codes() -> list[str]:
    """Alle geregistreerde providercodes."""
    return sorted(_REGISTRY)


def active_providers(enabled_codes: Iterable[str]) -> list[FlightProvider]:
    """Instantieer de adapters voor de gegeven (enabled) codes; sla onbekende over."""
    return [_REGISTRY[c]() for c in enabled_codes if c in _REGISTRY]


# Trigger registratie van de gebundelde adapters. Onderaan om circulaire import te vermijden
# (de adapters importeren `register` hierboven).
from app.providers import ryanair, travelpayouts, wizzair  # noqa: E402,F401
