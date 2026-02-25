"""Add access_logs table

Revision ID: a3b7c9e2f401
Revises: d9354085474a
Create Date: 2026-02-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3b7c9e2f401'
down_revision = 'd9354085474a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'access_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_type', sa.String(length=30), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('details', sa.String(length=200), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('access_logs')
