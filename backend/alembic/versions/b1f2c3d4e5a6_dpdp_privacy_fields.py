"""dpdp privacy fields (retention + consent proof)

Revision ID: b1f2c3d4e5a6
Revises: a8dfd65ac41f
Create Date: 2026-06-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1f2c3d4e5a6'
down_revision: Union[str, None] = 'a8dfd65ac41f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('events', sa.Column('retention_days', sa.Integer(), nullable=True))
    op.add_column('events', sa.Column('consent_text', sa.String(), nullable=True))
    op.add_column('guest_consents', sa.Column('consent_text', sa.String(), nullable=True))
    op.add_column('guest_consents', sa.Column('user_agent', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('guest_consents', 'user_agent')
    op.drop_column('guest_consents', 'consent_text')
    op.drop_column('events', 'consent_text')
    op.drop_column('events', 'retention_days')
