"""auth_tokens.purpose: 'session' toestaan (web-prefs sessietoken)

Revision ID: 0002_session_purpose
Revises: 87f352f6ec00
Create Date: 2026-06-16
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002_session_purpose"
down_revision: Union[str, None] = "87f352f6ec00"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = "purpose IN ('email_login','telegram_link')"
_NEW = "purpose IN ('email_login','telegram_link','session')"


def upgrade() -> None:
    op.drop_constraint("ck_auth_tokens_purpose", "auth_tokens", type_="check")
    op.create_check_constraint("ck_auth_tokens_purpose", "auth_tokens", _NEW)


def downgrade() -> None:
    op.drop_constraint("ck_auth_tokens_purpose", "auth_tokens", type_="check")
    op.create_check_constraint("ck_auth_tokens_purpose", "auth_tokens", _OLD)
