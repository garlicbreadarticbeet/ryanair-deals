"""Gebrande deal-kaart: PNG-rendering + de ondertekende /cards-endpoint (mail-hero)."""
from __future__ import annotations

import datetime
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from app.alerts import card as card_mod
from app.alerts.card import render_deal_card, signed_card_url
from app.channels.base import AlertItem
from app.core.combine import ReturnDeal
from app.core.scoring import score_deal
from app.settings import settings
from app.web.main import app

D1, D2 = datetime.date(2026, 7, 11), datetime.date(2026, 7, 14)


def _item():
    return AlertItem(
        deal=ReturnDeal("ryanair", "EIN", "BCN", 3, 34.0, D1, D2, 17, 17, airline="Ryanair", deeplink="x"),
        city_from="Eindhoven", city_to="Barcelona", country_to="es",
        score=score_deal(34.0, {"median_total": 80, "min_total": 34, "samples": 12, "days_span": 42}),
    )


@pytest.fixture
def client():
    return TestClient(app)


def test_render_deal_card_returns_png():
    png = render_deal_card(_item())
    assert png and png[:4] == b"\x89PNG"


def test_signed_url_requires_secret(monkeypatch):
    monkeypatch.setattr(settings, "alert_card_secret", "")
    assert signed_card_url(_item()) is None
    monkeypatch.setattr(settings, "alert_card_secret", "s3cret")
    url = signed_card_url(_item())
    assert url and "/cards/deal.png?" in url and "sig=" in url


def test_card_endpoint_valid_signature(client, monkeypatch):
    monkeypatch.setattr(settings, "alert_card_secret", "s3cret")
    url = signed_card_url(_item())
    path = urlparse(url).path + "?" + urlparse(url).query
    resp = client.get(path)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:4] == b"\x89PNG"


def test_card_endpoint_rejects_bad_signature(client, monkeypatch):
    monkeypatch.setattr(settings, "alert_card_secret", "s3cret")
    url = signed_card_url(_item())
    path = urlparse(url).path + "?" + urlparse(url).query
    assert client.get(path.replace("sig=", "sig=dead")).status_code == 404


def test_card_endpoint_off_without_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "alert_card_secret", "")
    resp = client.get("/cards/deal.png?price=%E2%82%AC34&city_to=Barcelona&sig=whatever")
    assert resp.status_code == 404


def test_render_card_graceful_without_fonts(monkeypatch):
    # Zonder fonts (of Pillow) faalt het niet hard: render geeft None terug.
    monkeypatch.setattr(card_mod, "_fonts", lambda: None)
    assert render_deal_card(_item()) is None
