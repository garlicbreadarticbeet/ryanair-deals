"""Billing-service met gemockte provider-calls (geen netwerk): Mollie én Lemon Squeezy.

Dekt checkout per provider, de Mollie-betaalwebhook en de Lemon Squeezy-webhook inclusief
signatuurverificatie (geldig → premium, ongeldig → geweigerd, expired → terug naar free).
"""
from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from sqlalchemy import select

import app.billing as billing
import app.lemonsqueezy as lemonsqueezy
import app.mollie as mollie
from app.billing import BillingError
from app.db.models import Subscription
from app.settings import settings


def _sub(db, user, **kw):
    kw.setdefault("provider", "mollie")
    sub = Subscription(user_id=user.id, **kw)
    db.add(sub)
    db.flush()
    return sub


def _get_sub(db, user) -> Subscription:
    return db.execute(select(Subscription).where(Subscription.user_id == user.id)).scalar_one()


# ============================ Mollie =====================================

def test_mollie_checkout_requires_price(db, make_user, monkeypatch):
    monkeypatch.setattr(settings, "billing_provider", "mollie")
    monkeypatch.setattr(settings, "premium_price_monthly", "")
    with pytest.raises(BillingError):
        billing.start_subscription_checkout(db, make_user(), "monthly")


def test_mollie_checkout_creates_customer_and_payment(db, make_user, monkeypatch):
    monkeypatch.setattr(settings, "billing_provider", "mollie")
    monkeypatch.setattr(mollie, "create_customer", lambda email=None, name=None: {"id": "cst_1"})
    monkeypatch.setattr(
        mollie, "create_first_payment",
        lambda **kw: {"_links": {"checkout": {"href": "https://pay.mollie/abc"}}},
    )
    user = make_user()

    url = billing.start_subscription_checkout(db, user, "annual")
    assert url == "https://pay.mollie/abc"
    sub = _get_sub(db, user)
    assert sub.provider == "mollie"
    assert sub.external_customer_id == "cst_1"
    assert sub.plan == "annual"
    assert sub.status == "pending"


def test_mollie_webhook_first_paid_activates_premium(db, make_user, monkeypatch):
    user = make_user(tier="free")
    _sub(db, user, external_customer_id="cst_9", status="pending", plan="monthly")
    monkeypatch.setattr(
        mollie, "get_payment",
        lambda pid: {"status": "paid", "sequenceType": "first", "customerId": "cst_9"},
    )
    monkeypatch.setattr(mollie, "create_subscription", lambda **kw: {"id": "sub_77"})

    billing.handle_mollie_webhook(db, "tr_1")

    assert user.tier == "premium"
    sub = _get_sub(db, user)
    assert sub.status == "active" and sub.external_subscription_id == "sub_77"


def test_mollie_webhook_first_failed_keeps_free(db, make_user, monkeypatch):
    user = make_user(tier="free")
    _sub(db, user, external_customer_id="cst_f", status="pending")
    monkeypatch.setattr(
        mollie, "get_payment",
        lambda pid: {"status": "failed", "sequenceType": "first", "customerId": "cst_f"},
    )

    billing.handle_mollie_webhook(db, "tr_2")

    assert user.tier == "free"
    assert _get_sub(db, user).status == "failed"


def test_mollie_webhook_recurring_failed_suspends(db, make_user, monkeypatch):
    user = make_user(tier="premium")
    _sub(db, user, external_customer_id="cst_r", external_subscription_id="sub_r", status="active")
    monkeypatch.setattr(
        mollie, "get_payment",
        lambda pid: {"status": "failed", "sequenceType": "recurring", "customerId": "cst_r"},
    )

    billing.handle_mollie_webhook(db, "tr_3")

    assert user.tier == "free"
    assert _get_sub(db, user).status == "suspended"


def test_mollie_cancel_downgrades(db, make_user, monkeypatch):
    monkeypatch.setattr(settings, "billing_provider", "mollie")
    user = make_user(tier="premium")
    _sub(db, user, external_customer_id="cst_c", external_subscription_id="sub_c", status="active")
    called = {}
    monkeypatch.setattr(
        mollie, "cancel_subscription",
        lambda cid, sid: called.update(cid=cid, sid=sid) or {},
    )

    billing.cancel_subscription(db, user)

    assert user.tier == "free"
    assert called == {"cid": "cst_c", "sid": "sub_c"}
    assert _get_sub(db, user).status == "canceled"


# ============================ Lemon Squeezy =====================================

def test_lemonsqueezy_checkout_returns_url(db, make_user, monkeypatch):
    # Standaardprovider is Lemon Squeezy; geen monkeypatch van billing_provider nodig.
    monkeypatch.setattr(settings, "lemonsqueezy_api_key", "k")
    monkeypatch.setattr(settings, "lemonsqueezy_store_id", "10")
    monkeypatch.setattr(settings, "lemonsqueezy_variant_annual", "v_year")
    captured = {}
    monkeypatch.setattr(
        lemonsqueezy, "create_checkout",
        lambda **kw: captured.update(kw) or "https://checkout.lemonsqueezy/xyz",
    )
    user = make_user(tier="free")

    url = billing.start_subscription_checkout(db, user, "annual")
    assert url == "https://checkout.lemonsqueezy/xyz"
    assert captured["store_id"] == "10" and captured["variant_id"] == "v_year"
    assert captured["user_id"] == user.id
    sub = _get_sub(db, user)
    assert sub.provider == "lemonsqueezy" and sub.plan == "annual" and sub.status == "pending"


def test_lemonsqueezy_checkout_requires_config(db, make_user, monkeypatch):
    monkeypatch.setattr(settings, "lemonsqueezy_api_key", "")
    with pytest.raises(BillingError):
        billing.start_subscription_checkout(db, make_user(), "annual")


def _ls_webhook(secret, *, event, status, user_id, sub_id="ls_sub_1", variant_id=None):
    """Bouw een Lemon Squeezy-webhookbody + bijbehorende geldige X-Signature."""
    payload = {
        "meta": {"event_name": event, "custom_data": {"user_id": str(user_id)}},
        "data": {"type": "subscriptions", "id": sub_id,
                 "attributes": {"status": status, "variant_id": variant_id}},
    }
    raw = json.dumps(payload).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return raw, sig


def test_lemonsqueezy_webhook_valid_signature_activates_premium(db, make_user, monkeypatch):
    monkeypatch.setattr(settings, "lemonsqueezy_webhook_secret", "whsec_test")
    monkeypatch.setattr(settings, "lemonsqueezy_variant_annual", "v_year")
    user = make_user(tier="free")
    raw, sig = _ls_webhook(
        "whsec_test", event="subscription_created", status="active",
        user_id=user.id, sub_id="ls_77", variant_id="v_year",
    )

    assert billing.handle_lemonsqueezy_webhook(db, raw, sig) is True
    assert user.tier == "premium"
    sub = _get_sub(db, user)
    assert sub.provider == "lemonsqueezy"
    assert sub.external_subscription_id == "ls_77"
    assert sub.plan == "annual" and sub.status == "active"


def test_lemonsqueezy_webhook_invalid_signature_rejected(db, make_user, monkeypatch):
    monkeypatch.setattr(settings, "lemonsqueezy_webhook_secret", "whsec_test")
    user = make_user(tier="free")
    raw, _ = _ls_webhook("whsec_test", event="subscription_created", status="active", user_id=user.id)

    assert billing.handle_lemonsqueezy_webhook(db, raw, "deadbeef") is False
    assert user.tier == "free"
    assert billing.get_subscription(db, user) is None  # niets aangemaakt/gewijzigd


def test_lemonsqueezy_webhook_non_ascii_signature_rejected(db, make_user, monkeypatch):
    # Een handtekening met non-ASCII tekens mag niet crashen (compare_digest), maar geweigerd worden.
    monkeypatch.setattr(settings, "lemonsqueezy_webhook_secret", "whsec_test")
    user = make_user(tier="free")
    raw, _ = _ls_webhook("whsec_test", event="subscription_created", status="active", user_id=user.id)

    assert billing.handle_lemonsqueezy_webhook(db, raw, "é-niet-ascii") is False
    assert user.tier == "free"


def test_lemonsqueezy_webhook_expired_downgrades_to_free(db, make_user, monkeypatch):
    monkeypatch.setattr(settings, "lemonsqueezy_webhook_secret", "whsec_test")
    user = make_user(tier="premium")
    _sub(db, user, provider="lemonsqueezy", external_subscription_id="ls_77", status="active")
    raw, sig = _ls_webhook(
        "whsec_test", event="subscription_expired", status="expired",
        user_id=user.id, sub_id="ls_77",
    )

    assert billing.handle_lemonsqueezy_webhook(db, raw, sig) is True
    assert user.tier == "free"
    assert _get_sub(db, user).status == "canceled"


def test_lemonsqueezy_webhook_unknown_event_ignored(db, make_user, monkeypatch):
    monkeypatch.setattr(settings, "lemonsqueezy_webhook_secret", "whsec_test")
    user = make_user(tier="free")
    raw, sig = _ls_webhook("whsec_test", event="order_created", status="paid", user_id=user.id)

    assert billing.handle_lemonsqueezy_webhook(db, raw, sig) is True
    assert user.tier == "free"  # niet-subscription-event verandert niets
