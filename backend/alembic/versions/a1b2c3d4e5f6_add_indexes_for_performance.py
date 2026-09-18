"""add_indexes_for_performance

Revision ID: a1b2c3d4e5f6
Revises: 36139ea90abf
Create Date: 2026-09-14 03:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '36139ea90abf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: adds indexes for Telegram support card lookup and ticket linking."""
    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.create_index(
            'ix_tickets_support_group_message_id',
            ['support_group_message_id'],
            unique=False,
            if_not_exists=True,
        )

    with op.batch_alter_table('knowledge_articles', schema=None) as batch_op:
        batch_op.create_index(
            'ix_knowledge_articles_source_ticket_id',
            ['source_ticket_id'],
            unique=False,
            if_not_exists=True,
        )


def downgrade() -> None:
    """Downgrade schema: drops performance indexes."""
    with op.batch_alter_table('knowledge_articles', schema=None) as batch_op:
        batch_op.drop_index('ix_knowledge_articles_source_ticket_id')

    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.drop_index('ix_tickets_support_group_message_id')
