"""pgvector embeddings

Revision ID: a8dfd65ac41f
Revises: 8f15aae7bc46
Create Date: 2026-06-13 13:29:53.186019

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8dfd65ac41f'
down_revision: Union[str, None] = '8f15aae7bc46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL-only: enable pgvector + add a 512-dim embedding column with a
    # cosine HNSW index for fast nearest-neighbour search.
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("ALTER TABLE face_embeddings ADD COLUMN IF NOT EXISTS embedding_vec vector(512)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_face_embeddings_vec "
        "ON face_embeddings USING hnsw (embedding_vec vector_cosine_ops)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_face_embeddings_vec")
    op.execute("ALTER TABLE face_embeddings DROP COLUMN IF EXISTS embedding_vec")
