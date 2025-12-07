"""Add jobs table

Revision ID: add_jobs_table
Revises: add_contract_cache
Create Date: 2025-12-07 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_jobs_table'
down_revision: Union[str, None] = 'add_contract_cache'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'jobs',
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('payment_id', sa.String(length=36), nullable=True),
        sa.Column('identifier_from_purchaser', sa.String(length=255), nullable=True),
        sa.Column('input_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('job_id')
    )
    op.create_index('idx_jobs_status', 'jobs', ['status'], unique=False)
    op.create_index('idx_jobs_payment_id', 'jobs', ['payment_id'], unique=False)
    op.create_index('idx_jobs_created_at', 'jobs', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_jobs_created_at', table_name='jobs')
    op.drop_index('idx_jobs_payment_id', table_name='jobs')
    op.drop_index('idx_jobs_status', table_name='jobs')
    op.drop_table('jobs')

