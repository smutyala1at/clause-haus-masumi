"""Add payment fields to jobs table

Revision ID: add_payment_fields
Revises: add_jobs_table
Create Date: 2025-12-07 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_payment_fields'
down_revision: Union[str, None] = 'add_jobs_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new payment-related columns
    op.add_column('jobs', sa.Column('blockchain_identifier', sa.String(length=255), nullable=True))
    op.add_column('jobs', sa.Column('payment_status', sa.String(length=20), nullable=True))
    
    # Create indexes for new columns
    op.create_index('idx_jobs_blockchain_id', 'jobs', ['blockchain_identifier'], unique=False)
    op.create_index('idx_jobs_payment_status', 'jobs', ['payment_status'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_jobs_payment_status', table_name='jobs')
    op.drop_index('idx_jobs_blockchain_id', table_name='jobs')
    
    # Drop columns
    op.drop_column('jobs', 'payment_status')
    op.drop_column('jobs', 'blockchain_identifier')

