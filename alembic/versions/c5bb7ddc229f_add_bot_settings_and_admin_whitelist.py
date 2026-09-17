"""add_bot_settings_and_admin_whitelist

Revision ID: c5bb7ddc229f
Revises: ca7fe8991c1f
Create Date: 2026-09-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5bb7ddc229f'
down_revision: Union[str, Sequence[str], None] = 'ca7fe8991c1f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: adds bot_settings (key/value) and bot_admin_whitelist tables."""
    op.create_table(
        'bot_settings',
        sa.Column('key', sa.String(length=100), primary_key=True),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'bot_admin_whitelist',
        sa.Column('user_id', sa.BigInteger(), primary_key=True),
        sa.Column('added_by', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema: drops bot_settings and bot_admin_whitelist tables."""
    op.drop_table('bot_admin_whitelist')
    op.drop_table('bot_settings')
