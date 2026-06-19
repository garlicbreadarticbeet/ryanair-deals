"""deal_price_points — prijsgeschiedenis per route (voedt de dealscore)

Revision ID: 0006_deal_price_points
Revises: 0005_billing_provider_agnostic
Create Date: 2026-06-20 10:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0006_deal_price_points"
down_revision: Union[str, None] = "0005_billing_provider_agnostic"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "deal_price_points",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("origin", sa.String(length=3), nullable=False),
        sa.Column("destination", sa.String(length=3), nullable=False),
        sa.Column("nights", sa.SmallInteger(), nullable=False),
        sa.Column("total_price", sa.Numeric(8, 2), nullable=False),
        sa.Column("observed_on", sa.Date(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "origin", "destination", "nights", "observed_on",
            name="uq_price_points_day",
        ),
    )
    op.create_index(
        "ix_price_points_route",
        "deal_price_points",
        ["provider", "origin", "destination", "nights", "observed_on"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_price_points_route", table_name="deal_price_points")
    op.drop_table("deal_price_points")
