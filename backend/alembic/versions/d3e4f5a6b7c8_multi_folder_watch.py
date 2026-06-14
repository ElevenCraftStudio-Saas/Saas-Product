"""allow multiple folder watches per event (drop unique on event_id)

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-06-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Replace the UNIQUE index on event_id with a plain (non-unique) one.
    op.drop_index('ix_folder_watches_event_id', table_name='folder_watches')
    op.create_index('ix_folder_watches_event_id', 'folder_watches', ['event_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_folder_watches_event_id', table_name='folder_watches')
    op.create_index('ix_folder_watches_event_id', 'folder_watches', ['event_id'], unique=True)
