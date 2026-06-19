"""Travelpayouts-adapter (retour-native pad) — parsing, filtering, affiliate-deeplink,
en de scan-integratie. Netwerk is gemockt; geen live API-calls.
"""
from __future__ import annotations

import datetime

from app.providers.base import ReturnFare
from app.providers.travelpayouts import TravelpayoutsProvider, _deeplink, _months_between
from app.settings import settings


class _Resp:
    def __init__(self, payload):
        self._p = payload
        self.status_code = 200

    def json(self):
        return self._p


class _FakeSession:
    """Geeft de canned records alleen terug voor destination=BCN (zodat de test één
    voorspelbare route oplevert i.p.v. één per bestemming)."""

    def __init__(self, records):
        self._records = records

    def get(self, url, params=None, timeout=None):
        if params.get("destination") == "BCN":
            return _Resp({"success": True, "data": self._records})
        return _Resp({"success": True, "data": []})


def test_months_between():
    assert _months_between(datetime.date(2026, 7, 15), datetime.date(2026, 9, 2)) == [
        "2026-07", "2026-08", "2026-09"
    ]


def test_deeplink_appends_marker():
    link = _deeplink("/search/EIN0208BCN0508?x=1", "741367")
    assert link == "https://www.aviasales.com/search/EIN0208BCN0508?x=1&marker=741367"
    assert _deeplink(None, "741367") is None


def test_no_token_returns_empty(monkeypatch):
    monkeypatch.setattr(settings, "travelpayouts_token", "")
    prov = TravelpayoutsProvider()
    out = list(prov.return_deals(
        ["EIN"], datetime.date(2026, 7, 1), datetime.date(2026, 9, 30), [3, 5, 7], "EUR"
    ))
    assert out == []


def test_return_deals_parses_filters_and_deeplink(monkeypatch):
    monkeypatch.setattr(settings, "travelpayouts_token", "tok")
    monkeypatch.setattr(settings, "travelpayouts_marker", "741367")
    monkeypatch.setattr(settings, "travelpayouts_market", "nl")
    monkeypatch.setattr(settings, "concurrency", 2)

    records = [
        # 3 nachten, €48 → de winnaar
        {"airline": "FR", "departure_at": "2026-08-02T10:00:00+02:00",
         "return_at": "2026-08-05T10:00:00+02:00", "price": 48,
         "link": "/search/EIN0208BCN05081?t=abc"},
        # zelfde route+nachten maar duurder → cheapest-merge gooit 'm weg
        {"airline": "FR", "departure_at": "2026-08-10T10:00:00+02:00",
         "return_at": "2026-08-13T10:00:00+02:00", "price": 70, "link": "/search/dup"},
        # 4 nachten → niet in trip_lengths
        {"airline": "W6", "departure_at": "2026-08-02T10:00:00+02:00",
         "return_at": "2026-08-06T10:00:00+02:00", "price": 30, "link": "/search/x"},
        # buiten de horizon
        {"airline": "FR", "departure_at": "2026-12-02T10:00:00+02:00",
         "return_at": "2026-12-05T10:00:00+02:00", "price": 19, "link": "/search/y"},
    ]
    prov = TravelpayoutsProvider()
    prov._session = _FakeSession(records)

    out = list(prov.return_deals(
        ["EIN"], datetime.date(2026, 7, 1), datetime.date(2026, 9, 30), [3, 5, 7], "EUR"
    ))

    assert len(out) == 1
    f = out[0]
    assert (f.origin, f.destination, f.nights, f.total) == ("EIN", "BCN", 3, 48.0)
    assert f.currency == "EUR"
    assert f.airline == "Ryanair"               # FR → leesbare naam
    assert f.deeplink.startswith("https://www.aviasales.com/search/EIN0208BCN05081")
    assert "marker=741367" in f.deeplink


def test_scan_persists_return_native_with_deeplink(db, make_user, monkeypatch):
    """De scan kiest het retour-native pad en slaat deeplink + airline op in deals."""
    from sqlalchemy import select

    from app.core.scan import run_scan
    from app.db.models import Deal, Provider, UserOrigin

    user = make_user(origins=[], threshold=100, trip_lengths=(3,))
    tp_id = db.execute(select(Provider.id).where(Provider.code == "travelpayouts")).scalar_one()
    db.add(UserOrigin(user_id=user.id, provider_id=tp_id, origin_iata="EIN"))
    db.flush()

    fare = ReturnFare(
        provider="travelpayouts", origin="EIN", destination="BCN", nights=3,
        out_date=datetime.date(2026, 8, 2), in_date=datetime.date(2026, 8, 5), total=48.0,
        currency="EUR", deeplink="https://www.aviasales.com/search/x?marker=741367",
        airline="Ryanair",
    )

    class _FakeProvider:
        code = "travelpayouts"

        def return_deals(self, *args, **kwargs):
            return [fare]

    monkeypatch.setattr("app.core.scan.get_provider", lambda code: _FakeProvider())

    deals = run_scan(db, today=datetime.date(2026, 7, 1))
    assert any(d.destination == "BCN" and d.deeplink and "marker=741367" in d.deeplink for d in deals)

    row = db.execute(
        select(Deal).where(Deal.provider == "travelpayouts", Deal.destination == "BCN")
    ).scalar_one()
    assert float(row.total_price) == 48.0
    assert row.airline == "Ryanair"
    assert row.deeplink and "marker=741367" in row.deeplink
