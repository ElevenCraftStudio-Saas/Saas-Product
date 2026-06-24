"""drop pending role: pending -> user, CHECK now admin|user only

Revision ID: f6a7b8c9d0e1
Revises: e4f5a6b7c8d9
Create Date: 2026-06-24
"""
from typing import Sequence, Union

from alembic import op

from app.core.role_migration import collapse_pending

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    collapse_pending(conn)
    if conn.dialect.name == "postgresql":
        op.drop_constraint("ck_users_role", "users", type_="check")
        op.create_check_constraint("ck_users_role", "users", "role IN ('admin','user')")


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.drop_constraint("ck_users_role", "users", type_="check")
        op.create_check_constraint("ck_users_role", "users", "role IN ('admin','user','pending')")
