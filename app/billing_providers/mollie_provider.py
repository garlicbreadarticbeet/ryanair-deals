"""MollieBillingProvider — abonnement via Mollie (customer + first payment + subscription).

Tweestaps: eerst een mandaat opzetten met een eerste betaling (checkout), daarna maakt de
Mollie-webhook (app.billing.handle_mollie_webhook) het terugkerende abonnement aan zodra het
mandaat staat. Hergebruikt de dunne client in app/mollie.py ongewijzigd. Blijft selecteerbaar
via ``BILLING_PROVIDER=mollie`` zodat we na KvK-inschrijving terug kunnen zonder herbouw.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app import mollie
from app.billing_providers.base import register_billing_provider
from app.db.models import User
from app.settings import settings


@register_billing_provider
class MollieBillingProvider:
    name = "mollie"

    def create_checkout(self, session: Session, user: User, plan: str) -> str:
        from app import billing

        price = settings.premium_price_for(plan)
        if not price:
            raise billing.BillingError("Premium-prijs niet ingesteld.")
        sub = billing.get_or_create_subscription(session, user)
        sub.provider = self.name
        sub.plan = plan
        if not sub.external_customer_id:
            customer = mollie.create_customer(email=user.email)
            sub.external_customer_id = customer["id"]
        sub.status = "pending"
        session.flush()

        payment = mollie.create_first_payment(
            customer_id=sub.external_customer_id,
            amount=price,
            currency=settings.premium_currency,
            description=settings.premium_description,
            redirect_url=f"{settings.app_base_url}/account?paid=1",
            webhook_url=f"{settings.app_base_url}/billing/webhook",
        )
        return payment["_links"]["checkout"]["href"]

    def cancel(self, session: Session, user: User) -> None:
        from app import billing

        sub = billing.get_subscription(session, user)
        if sub and sub.external_customer_id and sub.external_subscription_id:
            mollie.cancel_subscription(sub.external_customer_id, sub.external_subscription_id)
        billing.downgrade(session, user, sub, status="canceled")
