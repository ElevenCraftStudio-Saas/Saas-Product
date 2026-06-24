"""add ON DELETE cascade / set null to all foreign keys

Revision ID: j0e1f2a3b4c5
Revises: i9d0e1f2a3b4
Create Date: 2026-06-24

Postgres: DROP existing FK + ADD with ON DELETE ... NOT VALID, then VALIDATE.
NOT VALID/VALIDATE keeps the lock to a brief sub-second window (no table
rewrite) — run in a low-traffic window to be safe.
SQLite: cannot ALTER FKs; relies on ORM-level cascade (unchanged).
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = 'j0e1f2a3b4c5'
down_revision: Union[str, None] = 'i9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column, parent_table, parent_col, on_delete)
_FKS = [
    ("events", "photographer_id", "users", "id", "CASCADE"),
    ("photos", "event_id", "events", "id", "CASCADE"),
    ("face_embeddings", "photo_id", "photos", "id", "CASCADE"),
    ("face_embeddings", "event_id", "events", "id", "CASCADE"),
    ("downloads", "photo_id", "photos", "id", "CASCADE"),
    ("guest_consents", "event_id", "events", "id", "CASCADE"),
    ("folder_watches", "event_id", "events", "id", "CASCADE"),
    ("api_tokens", "user_id", "users", "id", "CASCADE"),
    ("activity_logs", "event_id", "events", "id", "SET NULL"),
    ("activity_logs", "photo_id", "photos", "id", "SET NULL"),
]


def _existing_fk_name(conn, table, column):
    return conn.execute(
        text(
            """
            SELECT tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name AND tc.table_name = kcu.table_name
            WHERE tc.table_name = :t AND tc.constraint_type = 'FOREIGN KEY'
              AND kcu.column_name = :c
            LIMIT 1
            """
        ),
        {"t": table, "c": column},
    ).scalar()


def _recreate(conn, table, column, ptable, pcol, on_delete):
    old = _existing_fk_name(conn, table, column)
    if old:
        op.execute(f'ALTER TABLE {table} DROP CONSTRAINT "{old}"')
    new = f"fk_{table}_{column}"
    op.execute(
        f'ALTER TABLE {table} ADD CONSTRAINT "{new}" '
        f'FOREIGN KEY ({column}) REFERENCES {ptable}({pcol}) ON DELETE {on_delete} NOT VALID'
    )
    op.execute(f'ALTER TABLE {table} VALIDATE CONSTRAINT "{new}"')


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return  # SQLite: ORM cascade only
    for table, column, ptable, pcol, on_delete in _FKS:
        _recreate(conn, table, column, ptable, pcol, on_delete)


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return
    for table, column, ptable, pcol, _on_delete in _FKS:
        op.execute(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS "fk_{table}_{column}"')
        op.execute(
            f'ALTER TABLE {table} ADD CONSTRAINT "fk_{table}_{column}" '
            f'FOREIGN KEY ({column}) REFERENCES {ptable}({pcol})'
        )
