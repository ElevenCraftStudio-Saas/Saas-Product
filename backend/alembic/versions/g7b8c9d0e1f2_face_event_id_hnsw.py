"""denormalize event_id onto face_embeddings + tuned HNSW for event-scoped KNN

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-24

Adds face_embeddings.event_id (backfilled from the photo->event join) so the
matching query can pre-filter by event and use the HNSW index for a KNN
ORDER BY ... LIMIT search. Rebuilds the HNSW index with tuned params.

NOTE: the HNSW rebuild briefly write-locks face_embeddings — run in a
low-traffic window (per Phase 2 design decision).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'g7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('face_embeddings', sa.Column('event_id', sa.Integer(), nullable=True))
    # Portable backfill (works on PostgreSQL and SQLite).
    op.execute(
        "UPDATE face_embeddings "
        "SET event_id = (SELECT event_id FROM photos WHERE photos.id = face_embeddings.photo_id)"
    )
    op.create_index('ix_face_embeddings_event_id', 'face_embeddings', ['event_id'])

    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        # Rebuild HNSW with tuned params (old index used pgvector defaults).
        op.execute("DROP INDEX IF EXISTS ix_face_embeddings_vec")
        op.execute(
            "CREATE INDEX ix_face_embeddings_vec ON face_embeddings "
            "USING hnsw (embedding_vec vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_face_embeddings_vec")
        op.execute(
            "CREATE INDEX ix_face_embeddings_vec ON face_embeddings "
            "USING hnsw (embedding_vec vector_cosine_ops)"
        )
    op.drop_index('ix_face_embeddings_event_id', table_name='face_embeddings')
    op.drop_column('face_embeddings', 'event_id')
