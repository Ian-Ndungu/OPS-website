"""Public clan join requests.
Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('clan_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('gamer_tag', sa.String(64), nullable=False),
        sa.Column('player_id', sa.String(80), nullable=False),
        sa.Column('game', sa.String(80), nullable=False),
        sa.Column('clan_tag', sa.String(32), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('contact', sa.String(100), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('screenshot', sa.LargeBinary(), nullable=False),
        sa.Column('screenshot_type', sa.String(32), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('review_note', sa.Text(), nullable=False),
        sa.Column('reviewed_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('reviewed_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_clan_requests_status', 'clan_requests', ['status'])


def downgrade():
    op.drop_index('ix_clan_requests_status', table_name='clan_requests')
    op.drop_table('clan_requests')
