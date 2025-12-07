"""Add contract analysis cache table

Revision ID: add_contract_cache
Revises: add_vector_index
Create Date: 2025-12-07 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_contract_cache'
down_revision: Union[str, None] = 'add_vector_index'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'contract_analysis_cache',
        sa.Column('id', sa.String(length=64), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('chunks', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('chunk_embeddings', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('openai_result', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('result_string', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_accessed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_contract_cache_job_id', 'contract_analysis_cache', ['job_id'], unique=False)
    op.create_index('idx_contract_cache_created_at', 'contract_analysis_cache', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_contract_cache_created_at', table_name='contract_analysis_cache')
    op.drop_index('idx_contract_cache_job_id', table_name='contract_analysis_cache')
    op.drop_table('contract_analysis_cache')

