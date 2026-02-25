"""Add model_residuals column to analysis_versions

Revision ID: d9354085474a
Revises: 81915dfa5605
Create Date: 2026-02-10 16:57:41.172479

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd9354085474a'
down_revision = '81915dfa5605'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('analysis_versions', sa.Column('model_residuals', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('analysis_versions', 'model_residuals')
