"""Durable public announcement and result images.
Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa
revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('public_images',
        sa.Column('path', sa.String(255), primary_key=True),
        sa.Column('content_type', sa.String(32), nullable=False),
        sa.Column('data', sa.LargeBinary(), nullable=False))


def downgrade():
    op.drop_table('public_images')
