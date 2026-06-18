"""contact_messages (publiek contactformulier)

Revision ID: 0003_contact_messages
Revises: 8ff93d5f4640
Create Date: 2026-06-19 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0003_contact_messages"
down_revision: Union[str, None] = "8ff93d5f4640"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contact_messages",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("message", sa.String(length=4000), nullable=False),
        sa.Column("handled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contact_messages_created", "contact_messages", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_contact_messages_created", table_name="contact_messages")
    op.drop_table("contact_messages")
