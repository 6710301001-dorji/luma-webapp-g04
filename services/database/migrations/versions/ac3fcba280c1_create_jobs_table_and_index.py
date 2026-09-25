"""create jobs table and index

Revision ID: ac3fcba280c1
Revises: c1a7f5d9e204
Create Date: 2026-09-24 14:30:46.527813

Alembic 1.19.1 keeps this named CHECK during SQLite batch table copies.
Unnamed CHECK constraints may be lost. If a later migration drops or renames
status, it must explicitly drop and recreate ck_jobs_status.

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ac3fcba280c1'
down_revision = 'c1a7f5d9e204'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('params', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=True),
        sa.Column('seed_used', sa.Integer(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'done', 'failed')",
            name='ck_jobs_status',
        ),
        sa.ForeignKeyConstraint(
            ['asset_id'], ['assets.id'],
            name='fk_jobs_asset_id_assets', ondelete='SET NULL',
        ),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'],
            name='fk_jobs_user_id_users', ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_jobs_status_created_at', 'jobs', ['status', 'created_at'])
    op.create_index('ix_jobs_user_id', 'jobs', ['user_id'])


def downgrade():
    op.drop_index('ix_jobs_user_id', table_name='jobs')
    op.drop_index('ix_jobs_status_created_at', table_name='jobs')
    op.drop_table('jobs')
