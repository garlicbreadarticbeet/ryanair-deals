"""Minimale web-API: health, magic-link-verificatie, voorkeuren-roundtrip, GDPR-delete.

De get_db-dependency wordt overschreven naar de transactionele test-sessie, zodat alles
na de test wordt teruggedraaid.
"""
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


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_request_magic_link_returns_202(client):
    # Geen Resend-key in test → e-mail niet echt verstuurd, maar token wel aangemaakt.
    resp = client.post("/auth/email", json={"email": "web@example.nl"})
    assert resp.status_code == 202
    assert resp.json()["status"] in {"verstuurd", "aangemaakt"}


def test_verify_then_prefs_roundtrip(db, client):
    raw = accounts.start_email_login(db, "web@example.nl")
    resp = client.get("/auth/verify", params={"token": raw})
    assert resp.status_code == 200
    session_token = resp.json()["session_token"]
    auth_header = {"Authorization": f"Bearer {session_token}"}

    resp = client.get("/prefs", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json()["threshold"] == 50.0
    assert resp.json()["origins"] == []

    resp = client.put(
        "/prefs", headers=auth_header,
        json={"threshold": 35, "origins": ["ein", "nrn"], "trip_lengths": [3, 5]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["threshold"] == 35.0
    assert set(body["origins"]) == {"EIN", "NRN"}
    assert body["trip_lengths"] == [3, 5]


def test_prefs_requires_valid_token(client):
    assert client.get("/prefs").status_code == 401
    assert client.get("/prefs", headers={"Authorization": "Bearer onzin"}).status_code == 401


def test_delete_me_removes_account(db, client):
    raw = accounts.start_email_login(db, "weg@example.nl")
    session_token = client.get("/auth/verify", params={"token": raw}).json()["session_token"]
    auth_header = {"Authorization": f"Bearer {session_token}"}

    assert client.delete("/me", headers=auth_header).status_code == 204
    # Account weg → sessietoken (cascade verwijderd) werkt niet meer.
    assert client.get("/prefs", headers=auth_header).status_code == 401
