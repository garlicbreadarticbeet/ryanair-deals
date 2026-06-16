"""De registry kent beide adapters; een nieuwe maatschappij = 1 bestand + registratie.
Beide adapters voldoen aan het FlightProvider-Protocol; de Wizz-stub levert (nog) niets.
"""
from __future__ import annotations

import datetime

from app.providers.base import FlightProvider
from app.providers.registry import active_providers, get_provider, registered_codes


def test_both_adapters_registered():
    codes = registered_codes()
    assert "ryanair" in codes
    assert "wizzair" in codes


def test_active_providers_filters_on_enabled_codes():
    provs = active_providers(["ryanair"])
    assert [p.code for p in provs] == ["ryanair"]
    # onbekende codes worden overgeslagen, niet gecrasht
    assert active_providers(["bestaatniet"]) == []


def test_adapters_conform_to_protocol():
    assert isinstance(get_provider("ryanair"), FlightProvider)
    assert isinstance(get_provider("wizzair"), FlightProvider)


def test_wizz_stub_returns_empty():
    w = get_provider("wizzair")
    today = datetime.date(2026, 6, 16)
    assert list(w.discover_routes(["EIN"], today, today)) == []
    assert list(w.daily_fares("EIN", "BCN", ["2026-07-01"], "EUR")) == []
