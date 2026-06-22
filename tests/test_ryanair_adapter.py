"""De Ryanair-adapter mapt de bron-JSON correct naar genormaliseerde types,
met dezelfde skip-regels als het bewezen fetch_perday (geen netwerk; sessie gemockt).
"""
from __future__ import annotations

import datetime
from types import SimpleNamespace

from app.providers.base import DailyFare, Route
from app.providers.ryanair import RyanairProvider


class _FakeResp:
    def __init__(self, status: int, payload: dict):
        self.status_code = status
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _FakeSession:
    def __init__(self, payload: dict):
        self._payload = payload
        self.calls: list = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return _FakeResp(200, self._payload)


def _provider_without_network() -> RyanairProvider:
    """RyanairProvider zonder __init__ (geen echte Ryanair-client / sessie)."""
    return object.__new__(RyanairProvider)


def test_daily_fares_mapping_and_skips():
    payload = {
        "outbound": {
            "fares": [
                {"day": "2026-07-01", "price": {"value": 19.99},
                 "soldOut": False, "unavailable": False,
                 "departureDate": "2026-07-01T06:00:00.000"},
                {"day": "2026-07-02", "price": {"value": 29.99}, "soldOut": True},      # skip
                {"day": "2026-07-03", "price": None},                                   # skip
                {"day": "2026-07-04", "price": {"value": 9.99}, "unavailable": True},   # skip
                {"day": "kapotte-datum", "price": {"value": 5.0}},                      # skip
                {"day": "2026-07-05", "price": {"value": 42.50}},                       # ok
            ]
        }
    }
    prov = _provider_without_network()
    prov._session = _FakeSession(payload)

    fares = list(prov.daily_fares("EIN", "BCN", ["2026-07-01"], "EUR"))

    assert len(fares) == 2
    f0 = fares[0]
    assert isinstance(f0, DailyFare)
    assert (f0.provider, f0.origin, f0.destination) == ("ryanair", "EIN", "BCN")
    assert f0.fly_date == datetime.date(2026, 7, 1)
    assert f0.price == 19.99 and f0.currency == "EUR"
    assert f0.departure == "2026-07-01T06:00:00.000"
    assert fares[1].fly_date == datetime.date(2026, 7, 5)
    # de juiste URL + params zijn aangeroepen
    url, params = prov._session.calls[0]
    assert url.endswith("/oneWayFares/EIN/BCN/cheapestPerDay")
    assert params == {"outboundMonthOfDate": "2026-07-01", "currency": "EUR"}


def test_daily_fares_non_200_yields_nothing():
    prov = _provider_without_network()

    class _Resp503(_FakeSession):
        def get(self, url, params=None, timeout=None):
            return _FakeResp(503, {})

    prov._session = _Resp503({})
    assert list(prov.daily_fares("EIN", "BCN", ["2026-07-01"], "EUR")) == []


def test_discover_routes_dedup_and_mapping():
    prov = _provider_without_network()
    flights = [
        SimpleNamespace(origin="EIN", originFull="Eindhoven", destination="BCN", destinationFull="Barcelona"),
        SimpleNamespace(origin="EIN", originFull="Eindhoven", destination="BCN", destinationFull="Barcelona"),  # dup
        SimpleNamespace(origin="EIN", originFull="Eindhoven", destination="AGP", destinationFull="Malaga"),
    ]
    prov._api = SimpleNamespace(get_cheapest_flights=lambda *a, **k: flights)

    routes = list(prov.discover_routes(["EIN"], datetime.date(2026, 6, 16), datetime.date(2026, 9, 16)))

    assert [r.destination for r in routes] == ["BCN", "AGP"]   # dedup behouden
    assert isinstance(routes[0], Route)
    assert routes[0].provider == "ryanair"
    assert routes[0].destination_name == "Barcelona"


def test_discover_routes_tolerant_on_error():
    """Een fout op één vertrekveld stopt de scan niet (zoals het origineel)."""
    prov = _provider_without_network()

    def _boom(*a, **k):
        raise RuntimeError("API down")

    prov._api = SimpleNamespace(get_cheapest_flights=_boom)
    assert list(prov.discover_routes(["EIN"], datetime.date(2026, 6, 16), datetime.date(2026, 9, 16))) == []


def test_booking_url_and_airline_name():
    prov = _provider_without_network()
    assert prov.airline_name == "Ryanair"
    url = prov.booking_url("EIN", "BCN", datetime.date(2026, 8, 19), datetime.date(2026, 8, 22))
    assert url.startswith("https://www.ryanair.com/")
    assert "originIata=EIN" in url and "destinationIata=BCN" in url
    assert "dateOut=2026-08-19" in url and "dateIn=2026-08-22" in url
    assert "isReturn=true" in url
