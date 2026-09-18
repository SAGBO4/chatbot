"""add_community_warnings_table

Revision ID: ca7fe8991c1f
Revises: a1b2c3d4e5f6
Create Date: 2026-09-17 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ca7fe8991c1f'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: adds the community_warnings table for /warn moderation."""
    op.create_table(
        'community_warnings',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('group_id', sa.BigInteger(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('warned_by', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    with op.batch_alter_table('community_warnings', schema=None) as batch_op:
        batch_op.create_index(
            'ix_community_warnings_user_id', ['user_id'], unique=False, if_not_exists=True
        )
        batch_op.create_index(
            'ix_community_warnings_group_id', ['group_id'], unique=False, if_not_exists=True
        )


def downgrade() -> None:
    """Downgrade schema: drops the community_warnings table."""
    with op.batch_alter_table('community_warnings', schema=None) as batch_op:
        batch_op.drop_index('ix_community_warnings_group_id')
        batch_op.drop_index('ix_community_warnings_user_id')
    op.drop_table('community_warnings')
