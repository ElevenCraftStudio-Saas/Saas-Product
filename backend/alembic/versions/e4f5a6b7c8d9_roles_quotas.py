"""roles + quotas + photo size, with role data remap

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-06-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.core.role_migration import remap_roles

revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('max_events', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('storage_limit_mb', sa.Integer(), nullable=True))
    op.add_column('photos', sa.Column('size_bytes', sa.Integer(), nullable=True))

    conn = op.get_bind()
    remap_roles(conn)

    # CHECK constraint is Postgres-only (SQLite can't ALTER ADD CHECK).
    if conn.dialect.name == "postgresql":
        op.create_check_constraint(
            "ck_users_role", "users", "role IN ('admin','user','pending')"
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column('photos', 'size_bytes')
    op.drop_column('users', 'storage_limit_mb')
    op.drop_column('users', 'max_events')
