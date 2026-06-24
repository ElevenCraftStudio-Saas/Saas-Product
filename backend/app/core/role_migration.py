"""Deterministic, idempotent role remap used by the e4f5a6b7c8d9 migration.

Old roles were `studio` (the bootstrap owner) and `guest` (everyone else).
New roles are `admin` / `user` / `pending`. The remap guarantees exactly one
admin (the lowest-id user) and never grants access a row didn't already have:
  - lowest-id user      -> admin
  - other 'studio' rows -> user
  - other 'guest' rows  -> pending

Kept in app code (not inline in the Alembic file) so it is unit-testable
against the SQLite test DB.
"""
from sqlalchemy import text


def remap_roles(conn) -> None:
    """Historical (migration e4f5a6b7c8d9): studio->user, guest->pending,
    lowest-id->admin. Kept for that migration's import; superseded by the
    pending removal (see collapse_pending)."""
    conn.execute(text("UPDATE users SET role='user' WHERE role='studio'"))
    conn.execute(text("UPDATE users SET role='pending' WHERE role='guest'"))
    row = conn.execute(text("SELECT id FROM users ORDER BY id ASC LIMIT 1")).fetchone()
    if row is not None:
        conn.execute(text("UPDATE users SET role='admin' WHERE id=:i"), {"i": row[0]})


def collapse_pending(conn) -> None:
    """Remove the 'pending' role: every pending user becomes a 'user'.
    Admins are untouched. Idempotent."""
    conn.execute(text("UPDATE users SET role='user' WHERE role='pending'"))
