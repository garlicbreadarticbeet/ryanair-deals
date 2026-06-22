"""auth_throttle — rate-limiting voor magic-link-mails (per e-mail/IP)

Revision ID: 0007_auth_throttle
Revises: 0006_deal_price_points
Create Date: 2026-06-22 12:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0007_auth_throttle"
down_revision: Union[str, None] = "0006_deal_price_points"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auth_throttle",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("scope", sa.String(length=8), nullable=False),
        sa.Column("identifier", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("scope IN ('email','ip')", name="ck_auth_throttle_scope"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auth_throttle_lookup",
        "auth_throttle",
        ["scope", "identifier", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_auth_throttle_lookup", table_name="auth_throttle")
    op.drop_table("auth_throttle")
