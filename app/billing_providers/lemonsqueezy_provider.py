"""LemonSqueezyBillingProvider — abonnement via Lemon Squeezy (Merchant of Record).

Eén checkout-stap: we sturen de klant naar een hosted checkout voor het juiste variant
(maand/jaar). De activatie/afschaling gebeurt via de webhook (app.billing.handle_lemonsqueezy_webhook).
Opzeggen gaat via DELETE /subscriptions/{id}; Lemon Squeezy laat het lopen tot einde periode.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app import lemonsqueezy
from app.billing_providers.base import register_billing_provider
from app.db.models import User
from app.settings import settings


@register_billing_provider
class LemonSqueezyBillingProvider:
    name = "lemonsqueezy"

    def create_checkout(self, session: Session, user: User, plan: str) -> str:
        from app import billing

        if not (settings.lemonsqueezy_api_key and settings.lemonsqueezy_store_id):
            raise billing.BillingError("Lemon Squeezy is nog niet geconfigureerd.")
        variant = settings.lemonsqueezy_variant_for(plan)
        if not variant:
            raise billing.BillingError("Geen Lemon Squeezy-variant voor dit plan ingesteld.")
        sub = billing.get_or_create_subscription(session, user)
        sub.provider = self.name
        sub.plan = plan
        sub.status = "pending"
        session.flush()
        return lemonsqueezy.create_checkout(
            store_id=settings.lemonsqueezy_store_id,
            variant_id=variant,
            email=user.email,
            user_id=user.id,
            redirect_url=f"{settings.app_base_url}/account?paid=1",
        )

    def cancel(self, session: Session, user: User) -> None:
        # Lemon Squeezy laat een opgezegd abonnement doorlopen tot ``ends_at``: we annuleren bij
        # de provider en markeren de rij, maar houden de toegang tot de 'expired'-webhook
        # afschaalt (vertrouwensregel: "je houdt toegang tot het einde van je periode").
        from app import billing

        sub = billing.get_subscription(session, user)
        if sub and sub.external_subscription_id:
            lemonsqueezy.cancel_subscription(sub.external_subscription_id)
        if sub is not None:
            sub.status = "canceled"
            session.flush()
