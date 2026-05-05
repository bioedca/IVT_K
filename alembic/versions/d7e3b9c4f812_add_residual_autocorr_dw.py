"""Add residual_autocorr_dw column (Durbin-Watson statistic).

Replaces Shapiro-Wilk normality with Durbin-Watson autocorrelation as the
primary shape diagnostic in the fit reliability filter. The old normality
column is kept for backward compatibility but is no longer consulted by the
evaluator.

Revision ID: d7e3b9c4f812
Revises: c5d2a8e3f701
Create Date: 2026-05-04 22:10:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd7e3b9c4f812'
down_revision = 'c5d2a8e3f701'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('fit_results', sa.Column('residual_autocorr_dw', sa.Float(), nullable=True))
    op.add_column('fit_result_archives', sa.Column('residual_autocorr_dw', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('fit_result_archives', 'residual_autocorr_dw')
    op.drop_column('fit_results', 'residual_autocorr_dw')
