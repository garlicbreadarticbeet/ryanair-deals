"""deals: deeplink + airline (retour-native bronnen, bv. Travelpayouts)

Revision ID: 0004_deal_deeplink_airline
Revises: 0003_contact_messages
Create Date: 2026-06-19 02:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0004_deal_deeplink_airline"
down_revision: Union[str, None] = "0003_contact_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("airline", sa.String(length=16), nullable=True))
    op.add_column("deals", sa.Column("deeplink", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column("deals", "deeplink")
    op.drop_column("deals", "airline")
