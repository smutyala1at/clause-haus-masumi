"""Increase blockchain_identifier column length

Revision ID: increase_blockchain_identifier
Revises: add_payment_fields
Create Date: 2025-12-10 12:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'increase_blockchain_identifier'
down_revision: Union[str, None] = 'add_payment_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Change blockchain_identifier from VARCHAR(255) to TEXT
    # Masumi blockchain identifiers can be very long (682+ characters)
    op.alter_column('jobs', 'blockchain_identifier',
                    type_=sa.Text(),
                    existing_type=sa.String(length=255),
                    existing_nullable=True)


def downgrade() -> None:
    # Revert back to VARCHAR(255) - note: this may fail if data exceeds 255 chars
    op.alter_column('jobs', 'blockchain_identifier',
                    type_=sa.String(length=255),
                    existing_type=sa.Text(),
                    existing_nullable=True)

