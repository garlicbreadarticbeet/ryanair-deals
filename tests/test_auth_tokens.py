"""Auth-token mechanics: eenmalig, met TTL, gehasht opgeslagen."""
from __future__ import annotations

from app.web import auth


def test_issue_and_consume_once(db):
    raw = auth.issue_token(db, "email_login", payload="reiziger@example.nl")
    token = auth.consume_token(db, raw, "email_login")
    assert token is not None
    assert token.payload == "reiziger@example.nl"
    # Eenmalig: tweede keer verbruiken lukt niet.
    assert auth.consume_token(db, raw, "email_login") is None


def test_wrong_purpose_rejected(db):
    raw = auth.issue_token(db, "email_login")
    assert auth.consume_token(db, raw, "telegram_link") is None


def test_expired_token_rejected(db):
    raw = auth.issue_token(db, "email_login", ttl_minutes=-1)  # al verlopen
    assert auth.consume_token(db, raw, "email_login") is None


def test_session_verify(db, make_user):
    user = make_user()
    raw = auth.issue_token(db, "session", user_id=user.id)
    assert auth.verify_session(db, raw) == user.id
    assert auth.verify_session(db, "onzin-token") is None
