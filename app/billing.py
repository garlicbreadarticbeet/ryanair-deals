"""Mollie-abonnementen: checkout starten, webhook afhandelen, opzeggen.

De premium-toegang (users.tier) wordt door de webhook bij- en afgeschaald; de
subscriptions-tabel houdt de Mollie-koppeling en levenscyclus bij. Mollie-calls lopen via
app/mollie.py (in tests gemockt).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import mollie
from app.db.models import Subscription, User
from app.settings import settings


class BillingError(Exception):
    """Checkout/abonnement kan niet starten (bv. prijs niet ingesteld)."""


def _webhook_url() -> str:
    return f"{settings.app_base_url}/billing/webhook"


def _get_or_create_subscription(session: Session, user: User) -> Subscription:
    sub = session.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    ).scalar_one_or_none()
    if sub is None:
        sub = Subscription(user_id=user.id, status="pending")
        session.add(sub)
        session.flush()
    return sub


def start_subscription_checkout(session: Session, user: User) -> str:
    """Zet (zo nodig) een Mollie-customer op + een eerste betaling; geef de checkout-URL terug."""
    if not settings.premium_price:
        raise BillingError("Premium-prijs niet ingesteld (PREMIUM_PRICE).")
    sub = _get_or_create_subscription(session, user)
    if not sub.mollie_customer_id:
        customer = mollie.create_customer(email=user.email)
        sub.mollie_customer_id = customer["id"]
    sub.status = "pending"
    session.flush()

    payment = mollie.create_first_payment(
        customer_id=sub.mollie_customer_id,
        amount=settings.premium_price,
        currency=settings.premium_currency,
        description=settings.premium_description,
        redirect_url=f"{settings.app_base_url}/billing/return",
        webhook_url=_webhook_url(),
    )
    return payment["_links"]["checkout"]["href"]


def handle_webhook(session: Session, payment_id: str) -> None:
    """Verwerk een Mollie-betaalwebhook: schaal tier op/af op basis van de betaalstatus."""
    payment = mollie.get_payment(payment_id)
    customer_id = payment.get("customerId")
    if not customer_id:
        return
    sub = session.execute(
        select(Subscription).where(Subscription.mollie_customer_id == customer_id)
    ).scalar_one_or_none()
    if sub is None:
        return
    user = session.get(User, sub.user_id)
    status = payment.get("status")
    sequence = payment.get("sequenceType")

    if status == "paid":
        # Mandaat staat na de eerste betaling → maak het terugkerende abonnement aan.
        if sequence == "first" and not sub.mollie_subscription_id:
            subscription = mollie.create_subscription(
                customer_id=customer_id,
                amount=settings.premium_price,
                currency=settings.premium_currency,
                interval=settings.premium_interval,
                description=settings.premium_description,
                webhook_url=_webhook_url(),
            )
            sub.mollie_subscription_id = subscription["id"]
        sub.status = "active"
        if user is not None:
            user.tier = "premium"
    elif status in ("failed", "expired", "canceled"):
        if sequence == "first":
            sub.status = "failed"  # premium nooit geactiveerd
        else:
            sub.status = "suspended"  # terugkerende incasso mislukt → afschalen
            if user is not None:
                user.tier = "free"
    session.flush()


def cancel_subscription(session: Session, user: User) -> None:
    """Zeg het abonnement op bij Mollie en schaal de gebruiker terug naar gratis."""
    sub = session.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    ).scalar_one_or_none()
    if sub and sub.mollie_customer_id and sub.mollie_subscription_id:
        mollie.cancel_subscription(sub.mollie_customer_id, sub.mollie_subscription_id)
    if sub:
        sub.status = "canceled"
    user.tier = "free"
    session.flush()
