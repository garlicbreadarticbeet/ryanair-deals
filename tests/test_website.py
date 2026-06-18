"""Server-rendered website (HTML). DB-dependency naar de transactionele test-sessie."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import accounts
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


# ---------- auth (W2) ----------

def test_login_form_renders(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "inloglink" in resp.text.lower()


def test_login_submit_shows_inbox_with_dev_link(client):
    resp = client.post("/login", data={"email": "web2@example.nl"})
    assert resp.status_code == 200
    assert "Check je inbox" in resp.text
    assert "/verify?token=" in resp.text  # geen e-mailprovider → dev-link zichtbaar


def test_verify_sets_cookie_and_redirects_to_dashboard(db, client):
    raw = accounts.start_email_login(db, "verify@example.nl")
    resp = client.get("/verify", params={"token": raw}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/dashboard"
    assert "gv_session=" in resp.headers.get("set-cookie", "")


def test_verify_invalid_token_shows_error(client):
    resp = client.get("/verify", params={"token": "bestaat-niet"})
    assert resp.status_code == 400
    assert "Ongeldige" in resp.text
