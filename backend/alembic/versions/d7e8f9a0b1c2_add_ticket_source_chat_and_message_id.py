"""add_ticket_source_chat_and_message_id

Revision ID: d7e8f9a0b1c2
Revises: c5bb7ddc229f
Create Date: 2026-09-30 07:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7e8f9a0b1c2'
down_revision: Union[str, Sequence[str], None] = 'c5bb7ddc229f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: adds source_chat_id and source_message_id to tickets table."""
    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source_chat_id', sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column('source_message_id', sa.BigInteger(), nullable=True))
        batch_op.create_index('ix_tickets_source_chat_id', ['source_chat_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema: removes source_chat_id and source_message_id from tickets table."""
    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.drop_index('ix_tickets_source_chat_id')
        batch_op.drop_column('source_message_id')
        batch_op.drop_column('source_chat_id')
