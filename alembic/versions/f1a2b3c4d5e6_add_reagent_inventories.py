"""Add reagent_inventories table (per-project reagent stock/final concentrations).

Creates a single-row-per-project inventory holding the stock and final
concentrations for every IVT reaction component. This is the source of truth the
calculator and project settings both read/write, replacing hardcoded lot defaults.

Revision ID: f1a2b3c4d5e6
Revises: d7e3b9c4f812
Create Date: 2026-06-23 00:00:00.000000
"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = 'd7e3b9c4f812'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'reagent_inventories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        # 10X Reaction buffer (X)
        sa.Column('buffer_stock_x', sa.Float(), nullable=False),
        sa.Column('buffer_final_x', sa.Float(), nullable=False),
        # MgCl2 (mM)
        sa.Column('mgcl2_stock_mm', sa.Float(), nullable=False),
        sa.Column('mgcl2_final_mm', sa.Float(), nullable=False),
        # NTPs (mM)
        sa.Column('gtp_stock_mm', sa.Float(), nullable=False),
        sa.Column('gtp_final_mm', sa.Float(), nullable=False),
        sa.Column('atp_stock_mm', sa.Float(), nullable=False),
        sa.Column('atp_final_mm', sa.Float(), nullable=False),
        sa.Column('ctp_stock_mm', sa.Float(), nullable=False),
        sa.Column('ctp_final_mm', sa.Float(), nullable=False),
        sa.Column('utp_stock_mm', sa.Float(), nullable=False),
        sa.Column('utp_final_mm', sa.Float(), nullable=False),
        # DFHBI dye (uM)
        sa.Column('dfhbi_stock_um', sa.Float(), nullable=False),
        sa.Column('dfhbi_final_um', sa.Float(), nullable=False),
        # Enzymes (U/uL)
        sa.Column('ppi_stock_u_ul', sa.Float(), nullable=False),
        sa.Column('ppi_final_u_ul', sa.Float(), nullable=False),
        sa.Column('rnasin_stock_u_ul', sa.Float(), nullable=False),
        sa.Column('rnasin_final_u_ul', sa.Float(), nullable=False),
        sa.Column('t7_stock_u_ul', sa.Float(), nullable=False),
        sa.Column('t7_final_u_ul', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', name='uq_reagent_inventories_project_id'),
    )


def downgrade() -> None:
    op.drop_table('reagent_inventories')
