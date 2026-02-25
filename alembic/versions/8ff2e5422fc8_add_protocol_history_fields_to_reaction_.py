"""add protocol history fields to reaction_setups and dna_additions

Revision ID: 8ff2e5422fc8
Revises: b078f506e286
Create Date: 2026-02-23 14:27:34.588801

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8ff2e5422fc8'
down_revision = 'b078f506e286'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ReactionSetup: new columns for protocol print fidelity
    with op.batch_alter_table('reaction_setups') as batch_op:
        batch_op.add_column(sa.Column('n_reactions', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('master_mix_per_tube_ul', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('ligand_stock_concentration_um', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('ligand_final_concentration_um', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('ligand_volume_per_rxn_ul', sa.Float(), nullable=True))

    # ReactionDNAAddition: ligand condition
    with op.batch_alter_table('reaction_dna_additions') as batch_op:
        batch_op.add_column(sa.Column('ligand_condition', sa.String(10), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('reaction_dna_additions') as batch_op:
        batch_op.drop_column('ligand_condition')

    with op.batch_alter_table('reaction_setups') as batch_op:
        batch_op.drop_column('ligand_volume_per_rxn_ul')
        batch_op.drop_column('ligand_final_concentration_um')
        batch_op.drop_column('ligand_stock_concentration_um')
        batch_op.drop_column('master_mix_per_tube_ul')
        batch_op.drop_column('n_reactions')
