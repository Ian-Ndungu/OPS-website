"""Require approval for new public registrations; preserve existing accounts.
Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('account_status', sa.String(20), nullable=False, server_default='active'))


def downgrade():
    op.drop_column('users', 'account_status')
