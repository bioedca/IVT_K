"""Add nM targeting columns to ReactionDNAAddition

Revision ID: f1f38b8268cf
Revises: 8ff2e5422fc8
Create Date: 2026-03-05 12:42:44.420656

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1f38b8268cf'
down_revision = '8ff2e5422fc8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('reaction_dna_additions', sa.Column('stock_concentration_nM', sa.Float(), nullable=True))
    op.add_column('reaction_dna_additions', sa.Column('plasmid_size_bp', sa.Integer(), nullable=True))
    op.add_column('reaction_dna_additions', sa.Column('achieved_nM', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('reaction_dna_additions', 'achieved_nM')
    op.drop_column('reaction_dna_additions', 'plasmid_size_bp')
    op.drop_column('reaction_dna_additions', 'stock_concentration_nM')
