"""create_initial_tables

Revision ID: 36139ea90abf
Revises: 
Create Date: 2026-09-14 00:47:53.391319

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '36139ea90abf'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: creates initial tables if they do not exist."""
    # Knowledge Articles table
    op.create_table(
        'knowledge_articles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('solution', sa.Text(), nullable=False),
        sa.Column('keywords', sa.Text(), nullable=True),
        sa.Column('source_ticket_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        if_not_exists=True,
    )

    # Tickets table
    op.create_table(
        'tickets',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('user_handle', sa.String(length=255), nullable=True),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('automated_answer', sa.Text(), nullable=True),
        sa.Column('solution', sa.Text(), nullable=True),
        sa.Column('resolved_by', sa.String(length=255), nullable=True),
        sa.Column('resolution_channel', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('support_group_message_id', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        if_not_exists=True,
    )
    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.create_index('ix_tickets_user_id', ['user_id'], unique=False, if_not_exists=True)
        batch_op.create_index('ix_tickets_status', ['status'], unique=False, if_not_exists=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.drop_index('ix_tickets_status')
        batch_op.drop_index('ix_tickets_user_id')
    op.drop_table('tickets')
    op.drop_table('knowledge_articles')
