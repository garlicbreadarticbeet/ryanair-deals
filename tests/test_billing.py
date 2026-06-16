"""Mollie-abonnementslogica met gemockte Mollie-calls (geen netwerk)."""
from __future__ import annotations

import pytest
from sqlalchemy import select

import app.billing as billing
import app.mollie as mollie
from app.billing import BillingError
from app.db.models import Subscription
from app.settings import settings


def _sub(db, user, **kw):
    sub = Subscription(user_id=user.id, **kw)
    db.add(sub)
    db.flush()
    return sub


def test_checkout_requires_price(db, make_user, monkeypatch):
    monkeypatch.setattr(settings, "premium_price", "")
    with pytest.raises(BillingError):
        billing.start_subscription_checkout(db, make_user())


def test_checkout_creates_customer_and_payment(db, make_user, monkeypatch):
    monkeypatch.setattr(settings, "premium_price", "2.99")
    monkeypatch.setattr(mollie, "create_customer", lambda email=None, name=None: {"id": "cst_1"})
    monkeypatch.setattr(
        mollie, "create_first_payment",
        lambda **kw: {"_links": {"checkout": {"href": "https://pay.mollie/abc"}}},
    )
    user = make_user()

    url = billing.start_subscription_checkout(db, user)
    assert url == "https://pay.mollie/abc"
    sub = db.execute(select(Subscription).where(Subscription.user_id == user.id)).scalar_one()
    assert sub.mollie_customer_id == "cst_1"
    assert sub.status == "pending"


def test_webhook_first_paid_activates_premium(db, make_user, monkeypatch):
    monkeypatch.setattr(settings, "premium_price", "2.99")
    user = make_user(tier="free")
    _sub(db, user, mollie_customer_id="cst_9", status="pending")
    monkeypatch.setattr(
        mollie, "get_payment",
        lambda pid: {"status": "paid", "sequenceType": "first", "customerId": "cst_9"},
    )
    monkeypatch.setattr(mollie, "create_subscription", lambda **kw: {"id": "sub_77"})

    billing.handle_webhook(db, "tr_1")

    assert user.tier == "premium"
    sub = db.execute(select(Subscription).where(Subscription.user_id == user.id)).scalar_one()
    assert sub.status == "active" and sub.mollie_subscription_id == "sub_77"


def test_webhook_first_failed_keeps_free(db, make_user, monkeypatch):
    user = make_user(tier="free")
    _sub(db, user, mollie_customer_id="cst_f", status="pending")
    monkeypatch.setattr(
        mollie, "get_payment",
        lambda pid: {"status": "failed", "sequenceType": "first", "customerId": "cst_f"},
    )

    billing.handle_webhook(db, "tr_2")

    assert user.tier == "free"
    sub = db.execute(select(Subscription).where(Subscription.user_id == user.id)).scalar_one()
    assert sub.status == "failed"


def test_webhook_recurring_failed_suspends(db, make_user, monkeypatch):
    user = make_user(tier="premium")
    _sub(db, user, mollie_customer_id="cst_r", mollie_subscription_id="sub_r", status="active")
    monkeypatch.setattr(
        mollie, "get_payment",
        lambda pid: {"status": "failed", "sequenceType": "recurring", "customerId": "cst_r"},
    )

    billing.handle_webhook(db, "tr_3")

    assert user.tier == "free"
    sub = db.execute(select(Subscription).where(Subscription.user_id == user.id)).scalar_one()
    assert sub.status == "suspended"


def test_cancel_subscription_downgrades(db, make_user, monkeypatch):
    user = make_user(tier="premium")
    _sub(db, user, mollie_customer_id="cst_c", mollie_subscription_id="sub_c", status="active")
    called = {}
    monkeypatch.setattr(
        mollie, "cancel_subscription",
        lambda cid, sid: called.update(cid=cid, sid=sid) or {},
    )

    billing.cancel_subscription(db, user)

    assert user.tier == "free"
    assert called == {"cid": "cst_c", "sid": "sub_c"}
    sub = db.execute(select(Subscription).where(Subscription.user_id == user.id)).scalar_one()
    assert sub.status == "canceled"
