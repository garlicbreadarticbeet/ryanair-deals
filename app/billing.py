"""Provider-agnostische billing-service: kies provider, beheer de subscription-rij, flip de tier.

``settings.billing_provider`` bepaalt welke provider (Lemon Squeezy of Mollie) een checkout
start en opzegt; de provider-specifieke clients staan in app/lemonsqueezy.py en app/mollie.py,
de adapters in app/billing_providers/. De premium-toegang zit in ``users.tier`` en wordt op
één plek op-/afgeschaald: ``upgrade()`` / ``downgrade()``. De webhooks (per provider een eigen
functie) gebruiken diezelfde helpers.
"""
from __future__ import annotations

import datetime
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import lemonsqueezy, mollie
from app.billing_providers import base as providers
from app.db.models import Subscription, User
from app.settings import settings

_PLANS = ("monthly", "annual")

# Lemon Squeezy-status → onze subscription-status, voor de gevallen mét premium-toegang.
# 'cancelled' telt mee: opgezegd maar loopt door tot ``ends_at`` (afschalen pas bij 'expired').
_LS_ACTIVE = {"active": "active", "on_trial": "active", "cancelled": "canceled"}
# Lemon Squeezy-status → onze subscription-status, voor de gevallen zónder premium-toegang.
_LS_INACTIVE = {"expired": "canceled", "unpaid": "suspended", "paused": "suspended"}


class BillingError(Exception):
    """Checkout/abonnement kan niet starten (bv. prijs of provider niet geconfigureerd)."""


# ---------- subscription-rij (provider-agnostisch) ----------

def get_subscription(session: Session, user: User) -> Subscription | None:
    return session.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    ).scalar_one_or_none()


def get_or_create_subscription(session: Session, user: User) -> Subscription:
    sub = get_subscription(session, user)
    if sub is None:
        sub = Subscription(user_id=user.id, provider=settings.billing_provider, status="pending")
        session.add(sub)
        session.flush()
    return sub


# ---------- tier-flip op één plek ----------

def upgrade(
    session: Session,
    user: User,
    sub: Subscription,
    *,
    external_subscription_id: str | None = None,
    plan: str | None = None,
    status: str = "active",
) -> None:
    """De ENIGE plek die opschaalt: zet de subscription actief + user.tier='premium'."""
    sub.status = status
    if external_subscription_id is not None:
        sub.external_subscription_id = external_subscription_id
    if plan is not None:
        sub.plan = plan
    user.tier = "premium"
    session.flush()


def downgrade(
    session: Session, user: User, sub: Subscription | None, *, status: str = "canceled"
) -> None:
    """De ENIGE plek die afschaalt: zet de subscription-status + user.tier='free'."""
    if sub is not None:
        sub.status = status
    user.tier = "free"
    session.flush()


# ---------- provider-keuze + checkout/opzeggen ----------

def _provider() -> providers.BillingProvider:
    provider = providers.get_billing_provider(settings.billing_provider)
    if provider is None:
        raise BillingError(f"Onbekende betaalprovider: {settings.billing_provider!r}")
    return provider


def _normalize_plan(plan: str | None) -> str:
    return plan if plan in _PLANS else "annual"


def start_subscription_checkout(session: Session, user: User, plan: str = "annual") -> str:
    """Start een checkout via de actieve provider voor het gekozen plan; geef de checkout-URL terug."""
    return _provider().create_checkout(session, user, _normalize_plan(plan))


def cancel_subscription(session: Session, user: User) -> None:
    """Zeg het abonnement op via de actieve provider en schaal terug naar gratis."""
    _provider().cancel(session, user)


# ---------- Mollie-webhook ----------

def handle_mollie_webhook(session: Session, payment_id: str) -> None:
    """Verwerk een Mollie-betaalwebhook: schaal tier op/af op basis van de betaalstatus."""
    payment = mollie.get_payment(payment_id)
    customer_id = payment.get("customerId")
    if not customer_id:
        return
    sub = session.execute(
        select(Subscription).where(Subscription.external_customer_id == customer_id)
    ).scalar_one_or_none()
    if sub is None:
        return
    user = session.get(User, sub.user_id)
    if user is None:
        return
    status = payment.get("status")
    sequence = payment.get("sequenceType")
    plan = sub.plan or "monthly"

    if status == "paid":
        # Mandaat staat na de eerste betaling → maak het terugkerende abonnement aan.
        if sequence == "first" and not sub.external_subscription_id:
            subscription = mollie.create_subscription(
                customer_id=customer_id,
                amount=settings.premium_price_for(plan),
                currency=settings.premium_currency,
                interval=settings.mollie_interval_for(plan),
                description=settings.premium_description,
                webhook_url=f"{settings.app_base_url}/billing/webhook",
            )
            upgrade(session, user, sub, external_subscription_id=subscription["id"])
        else:
            upgrade(session, user, sub)
    elif status in ("failed", "expired", "canceled"):
        if sequence == "first":
            sub.status = "failed"  # premium nooit geactiveerd
            session.flush()
        else:
            downgrade(session, user, sub, status="suspended")  # terugkerende incasso mislukt


# ---------- Lemon Squeezy-webhook ----------

def _parse_iso(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _plan_from_variant(variant_id) -> str | None:
    vid = str(variant_id) if variant_id is not None else ""
    if vid and vid == str(settings.lemonsqueezy_variant_annual):
        return "annual"
    if vid and vid == str(settings.lemonsqueezy_variant_monthly):
        return "monthly"
    return None


def handle_lemonsqueezy_webhook(session: Session, raw_body: bytes, signature: str | None) -> bool:
    """Verwerk een Lemon Squeezy-webhook. Geeft False terug bij een ongeldige signatuur (weigeren).

    Verifieert ``X-Signature`` (HMAC-SHA256 over de rauwe body), leest ``meta.event_name``,
    ``meta.custom_data.user_id`` en ``data.attributes.status`` en schaalt de tier op/af.
    Onbekende events/statussen worden genegeerd; we crashen nooit op een webhook.
    """
    if not lemonsqueezy.verify_signature(raw_body, signature):
        return False
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return True  # signatuur ok, maar niets bruikbaars → genegeerd

    meta = payload.get("meta") or {}
    event = meta.get("event_name") or ""
    if not event.startswith("subscription"):
        return True  # orders/license-keys e.d. negeren we

    custom = meta.get("custom_data") or {}
    user_id = custom.get("user_id")
    data = payload.get("data") or {}
    attrs = data.get("attributes") or {}
    status = attrs.get("status")
    if user_id is None or status is None:
        return True

    try:
        user = session.get(User, int(user_id))
    except (TypeError, ValueError):
        user = None
    if user is None:
        return True

    sub = get_or_create_subscription(session, user)
    sub.provider = "lemonsqueezy"
    if data.get("id"):
        sub.external_subscription_id = str(data["id"])
    if attrs.get("customer_id") is not None:
        sub.external_customer_id = str(attrs["customer_id"])
    plan = _plan_from_variant(attrs.get("variant_id"))
    if plan:
        sub.plan = plan
    sub.current_period_end = _parse_iso(attrs.get("ends_at")) or _parse_iso(attrs.get("renews_at"))

    if status in _LS_ACTIVE:
        upgrade(session, user, sub, plan=plan, status=_LS_ACTIVE[status])
    elif status in _LS_INACTIVE:
        downgrade(session, user, sub, status=_LS_INACTIVE[status])
    else:
        session.flush()  # onbekende status: alleen de koppeling bijwerken
    return True
