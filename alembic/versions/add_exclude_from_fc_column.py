"""Add exclude_from_fc column to wells table

Revision ID: add_exclude_from_fc
Revises: 22ec2d6034b4
Create Date: 2026-02-03

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_exclude_from_fc'
down_revision = '22ec2d6034b4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add exclude_from_fc column to wells table
    # This column is used to flag wells with low R² that should be excluded
    # from fold change calculations
    op.add_column(
        'wells',
        sa.Column('exclude_from_fc', sa.Boolean(), nullable=False, server_default='0')
    )


def downgrade() -> None:
    op.drop_column('wells', 'exclude_from_fc')
