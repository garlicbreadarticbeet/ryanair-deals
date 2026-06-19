"""Server-rendered website (HTML). DB-dependency naar de transactionele test-sessie."""
from __future__ import annotations

import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import app.mollie as mollie
from app import accounts
from app.db.models import Deal, Subscription, User, UserOrigin
from app.settings import settings
from app.web import auth as webauth
from app.web.main import app, get_db


def _login(client, db, user):
    """Zet een geldige session-cookie voor deze gebruiker."""
    token = webauth.issue_token(db, "session", user_id=user.id)
    client.cookies.set("gv_session", token)
    return client


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


# ---------- dashboard / voorkeuren / kanalen (W3) ----------

def test_dashboard_requires_login(client):
    resp = client.get("/dashboard", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_dashboard_prompts_without_origins(db, client, make_user):
    user = make_user(origins=[])
    _login(client, db, user)
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "geen vertrekvelden" in resp.text.lower()


def test_dashboard_lists_matching_deals(db, client, make_user):
    user = make_user(origins=["EIN"], threshold=50)
    _login(client, db, user)
    db.add(Deal(provider="ryanair", origin="EIN", destination="BCN", nights=3,
                out_date=datetime.date(2026, 8, 1), in_date=datetime.date(2026, 8, 4),
                out_price=Decimal("20"), in_price=Decimal("15"),
                total_price=Decimal("35"), currency="EUR"))
    db.flush()
    resp = client.get("/dashboard")
    assert "EIN ⇄ BCN" in resp.text
    assert "35.00" in resp.text


def test_preferences_get_and_save_premium(db, client, make_user):
    user = make_user(origins=["EIN"], tier="premium")
    _login(client, db, user)
    assert "EIN" in client.get("/preferences").text

    resp = client.post("/preferences", data={
        "origins": "EIN NRN", "threshold": "40", "trip_lengths": "3 5",
        "alert_mode": "instant", "dest_filter_mode": "all",
    })
    assert resp.status_code == 200
    assert "opgeslagen" in resp.text.lower()
    origins = set(db.execute(select(UserOrigin.origin_iata).where(UserOrigin.user_id == user.id)).scalars())
    assert origins == {"EIN", "NRN"}


def test_preferences_free_origin_limit_message(db, client, make_user):
    user = make_user(origins=["EIN"], tier="free")
    _login(client, db, user)
    resp = client.post("/preferences", data={
        "origins": "EIN NRN", "threshold": "50", "trip_lengths": "3 5 7",
        "alert_mode": "digest", "dest_filter_mode": "all",
    })
    assert "premium" in resp.text.lower()


def test_channels_shows_telegram_connect(db, client, make_user, monkeypatch):
    # Onafhankelijk van de lokale .env: forceer 'geen bot-username' → handmatige instructie.
    monkeypatch.setattr(settings, "telegram_bot_username", "")
    user = make_user(origins=["EIN"])
    _login(client, db, user)
    resp = client.get("/channels")
    assert resp.status_code == 200
    assert "/start" in resp.text  # geen bot-username → handmatige koppelinstructie


def test_channels_whatsapp_gated_for_free(db, client, make_user):
    user = make_user(origins=["EIN"], tier="free")
    _login(client, db, user)
    assert "Upgrade" in client.get("/channels").text


# ---------- account + billing (W4) ----------

def test_account_free_shows_upgrade(db, client, make_user):
    _login(client, db, make_user(origins=["EIN"], tier="free"))
    resp = client.get("/account")
    assert resp.status_code == 200
    assert "Upgrade nu" in resp.text


def test_account_premium_shows_cancel(db, client, make_user):
    _login(client, db, make_user(origins=["EIN"], tier="premium"))
    assert "opzeggen" in client.get("/account").text.lower()


def test_upgrade_redirects_to_mollie(db, client, make_user, monkeypatch):
    monkeypatch.setattr(settings, "premium_price", "2.99")
    monkeypatch.setattr(mollie, "create_customer", lambda email=None, name=None: {"id": "cst_w"})
    monkeypatch.setattr(
        mollie, "create_first_payment",
        lambda **kw: {"_links": {"checkout": {"href": "https://pay.mollie/web"}}},
    )
    _login(client, db, make_user(origins=["EIN"], tier="free"))
    resp = client.post("/upgrade", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "https://pay.mollie/web"


def test_upgrade_without_price_shows_error(db, client, make_user, monkeypatch):
    monkeypatch.setattr(settings, "premium_price", "")
    _login(client, db, make_user(origins=["EIN"], tier="free"))
    resp = client.post("/upgrade")
    assert "prijs" in resp.text.lower()


def test_cancel_downgrades_to_free(db, client, make_user, monkeypatch):
    user = make_user(origins=["EIN"], tier="premium")
    db.add(Subscription(user_id=user.id, mollie_customer_id="cst_x",
                        mollie_subscription_id="sub_x", status="active"))
    db.flush()
    monkeypatch.setattr(mollie, "cancel_subscription", lambda cid, sid: {})
    _login(client, db, user)

    resp = client.post("/billing/cancel", follow_redirects=False)
    assert resp.status_code == 303 and resp.headers["location"] == "/account"
    assert user.tier == "free"


def test_account_delete_removes_user(db, client, make_user):
    user = make_user(origins=["EIN"])
    uid = user.id
    _login(client, db, user)

    resp = client.post("/account/delete", follow_redirects=False)
    assert resp.status_code == 303 and resp.headers["location"] == "/"
    assert db.get(User, uid) is None


# ---------- luchthaven-zoeken (voor de vriendelijke /preferences) ----------

def test_airport_search(client):
    resp = client.get("/api/airports", params={"q": "eind"})
    assert resp.status_code == 200
    data = resp.json()
    assert any(a["iata"] == "EIN" for a in data)
    assert data and data[0]["label"]               # "Naam (CODE)" voor de chip
    assert client.get("/api/airports", params={"q": ""}).json() == []  # lege query → niks
