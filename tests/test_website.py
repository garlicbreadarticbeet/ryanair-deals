"""Server-rendered website (HTML). DB-dependency naar de transactionele test-sessie."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.web.main import app, get_db


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_landing_renders_for_anonymous(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Goedkoop" in resp.text
    assert "Gratis aanmelden" in resp.text  # niet-ingelogde CTA


def test_static_css_served(client):
    assert client.get("/static/style.css").status_code == 200


def test_logout_redirects_home(client):
    resp = client.get("/logout", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
