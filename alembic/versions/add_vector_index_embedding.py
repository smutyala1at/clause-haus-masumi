"""Add vector index on embedding column

Revision ID: add_vector_index
Revises: dcbd9fceaea3
Create Date: 2025-12-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_vector_index'
down_revision: Union[str, None] = 'dcbd9fceaea3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create HNSW index on embedding column for fast similarity searches
    # HNSW is faster for similarity search than IVFFlat
    # m=16, ef_construction=64 are good defaults for 1536-dimensional vectors
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_bgb_embeddings_embedding_hnsw 
        ON bgb_embeddings 
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)


def downgrade() -> None:
    op.drop_index('idx_bgb_embeddings_embedding_hnsw', table_name='bgb_embeddings')

