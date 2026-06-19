"""subscriptions provider-agnostisch + whatsapp uit de kanaaltypes

Maakt de subscriptions-tabel onafhankelijk van Mollie: generieke ``provider`` +
``external_customer_id``/``external_subscription_id`` (de oude ``mollie_*``-kolommen worden
overgezet en verwijderd) en een ``plan``-kolom (monthly/annual). Daarnaast verdwijnt WhatsApp
als toegestaan kanaaltype (channels.ck_channels_type).

Revision ID: 0005_billing_provider_agnostic
Revises: 0004_deal_deeplink_airline
Create Date: 2026-06-19 12:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0005_billing_provider_agnostic"
down_revision: Union[str, None] = "0004_deal_deeplink_airline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- channels: WhatsApp uit de toegestane kanaaltypes ---
    op.drop_constraint("ck_channels_type", "channels", type_="check")
    op.create_check_constraint("ck_channels_type", "channels", "type IN ('telegram','email')")

    # --- subscriptions: provider-agnostisch maken ---
    op.add_column(
        "subscriptions",
        sa.Column("provider", sa.String(length=32), server_default=sa.text("'lemonsqueezy'"), nullable=False),
    )
    op.add_column("subscriptions", sa.Column("external_customer_id", sa.String(length=64), nullable=True))
    op.add_column("subscriptions", sa.Column("external_subscription_id", sa.String(length=64), nullable=True))
    op.add_column("subscriptions", sa.Column("plan", sa.String(length=16), nullable=True))
    op.create_check_constraint(
        "ck_subscriptions_plan", "subscriptions", "plan IS NULL OR plan IN ('monthly','annual')"
    )

    # Bestaande Mollie-koppelingen overzetten naar de generieke kolommen (en provider markeren).
    op.execute(
        "UPDATE subscriptions "
        "SET external_customer_id = mollie_customer_id, "
        "    external_subscription_id = mollie_subscription_id, "
        "    provider = 'mollie' "
        "WHERE mollie_customer_id IS NOT NULL OR mollie_subscription_id IS NOT NULL"
    )

    op.drop_column("subscriptions", "mollie_subscription_id")
    op.drop_column("subscriptions", "mollie_customer_id")


def downgrade() -> None:
    # --- subscriptions: terug naar de Mollie-specifieke kolommen ---
    op.add_column("subscriptions", sa.Column("mollie_customer_id", sa.String(length=64), nullable=True))
    op.add_column("subscriptions", sa.Column("mollie_subscription_id", sa.String(length=64), nullable=True))
    # Alleen écht-Mollie-rijen terugzetten; een Lemon Squeezy-ID mag nooit in een mollie_*-kolom belanden.
    op.execute(
        "UPDATE subscriptions "
        "SET mollie_customer_id = external_customer_id, "
        "    mollie_subscription_id = external_subscription_id "
        "WHERE provider = 'mollie'"
    )
    op.drop_constraint("ck_subscriptions_plan", "subscriptions", type_="check")
    op.drop_column("subscriptions", "plan")
    op.drop_column("subscriptions", "external_subscription_id")
    op.drop_column("subscriptions", "external_customer_id")
    op.drop_column("subscriptions", "provider")

    # --- channels: WhatsApp weer toestaan ---
    op.drop_constraint("ck_channels_type", "channels", type_="check")
    op.create_check_constraint(
        "ck_channels_type", "channels", "type IN ('telegram','email','whatsapp')"
    )
