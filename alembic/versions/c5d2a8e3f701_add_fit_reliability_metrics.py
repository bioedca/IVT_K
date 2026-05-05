"""Add fit reliability metrics columns

Adds run_length_min, pct_plateau_reached, mean_signal to fit_results and
fit_result_archives tables. Used by the new fit reliability filter UI.

Revision ID: c5d2a8e3f701
Revises: f1f38b8268cf
Create Date: 2026-05-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c5d2a8e3f701'
down_revision = 'f1f38b8268cf'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('fit_results', sa.Column('run_length_min', sa.Float(), nullable=True))
    op.add_column('fit_results', sa.Column('pct_plateau_reached', sa.Float(), nullable=True))
    op.add_column('fit_results', sa.Column('mean_signal', sa.Float(), nullable=True))

    op.add_column('fit_result_archives', sa.Column('run_length_min', sa.Float(), nullable=True))
    op.add_column('fit_result_archives', sa.Column('pct_plateau_reached', sa.Float(), nullable=True))
    op.add_column('fit_result_archives', sa.Column('mean_signal', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('fit_result_archives', 'mean_signal')
    op.drop_column('fit_result_archives', 'pct_plateau_reached')
    op.drop_column('fit_result_archives', 'run_length_min')

    op.drop_column('fit_results', 'mean_signal')
    op.drop_column('fit_results', 'pct_plateau_reached')
    op.drop_column('fit_results', 'run_length_min')
