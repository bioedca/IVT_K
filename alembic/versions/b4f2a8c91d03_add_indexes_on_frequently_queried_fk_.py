"""add indexes on frequently queried FK columns

Revision ID: b4f2a8c91d03
Revises: 09354998e331
Create Date: 2026-02-20 10:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'b4f2a8c91d03'
down_revision = '09354998e331'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index('ix_well_assignments_construct_id', 'well_assignments', ['construct_id'])
    op.create_index('ix_wells_construct_id', 'wells', ['construct_id'])
    op.create_index('ix_wells_plate_id', 'wells', ['plate_id'])
    op.create_index('ix_hierarchical_results_construct_id', 'hierarchical_results', ['construct_id'])
    op.create_index('ix_fold_changes_test_well_id', 'fold_changes', ['test_well_id'])
    op.create_index('ix_fold_changes_control_well_id', 'fold_changes', ['control_well_id'])


def downgrade() -> None:
    op.drop_index('ix_fold_changes_control_well_id', 'fold_changes')
    op.drop_index('ix_fold_changes_test_well_id', 'fold_changes')
    op.drop_index('ix_hierarchical_results_construct_id', 'hierarchical_results')
    op.drop_index('ix_wells_plate_id', 'wells')
    op.drop_index('ix_wells_construct_id', 'wells')
    op.drop_index('ix_well_assignments_construct_id', 'well_assignments')
