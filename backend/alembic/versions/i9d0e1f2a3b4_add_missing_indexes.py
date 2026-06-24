"""add missing indexes (downloads.photo_id, activity composite, consents composite)

Revision ID: i9d0e1f2a3b4
Revises: h8c9d0e1f2a3
Create Date: 2026-06-24

Postgres: built CONCURRENTLY (no write lock, no maintenance window).
SQLite: plain CREATE INDEX.
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'i9d0e1f2a3b4'
down_revision: Union[str, None] = 'h8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = [
    ("ix_downloads_photo_id", "downloads", "photo_id"),
    ("ix_activity_event_created", "activity_logs", "event_id, created_at"),
    ("ix_consents_event_ip", "guest_consents", "event_id, ip_address"),
]


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        # CONCURRENTLY can't run inside a transaction.
        with op.get_context().autocommit_block():
            for name, table, cols in _INDEXES:
                op.execute(f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {name} ON {table} ({cols})")
    else:
        for name, table, cols in _INDEXES:
            op.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({cols})")


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            for name, _table, _cols in _INDEXES:
                op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
    else:
        for name, _table, _cols in _INDEXES:
            op.execute(f"DROP INDEX IF EXISTS {name}")
