"""Add admin action notes to service memo

Revision ID: e5b8c3d7a114
Revises: d2f4b7a91c8e
Create Date: 2026-02-27 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5b8c3d7a114'
down_revision = 'd2f4b7a91c8e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('service_memo', schema=None) as batch_op:
        batch_op.add_column(sa.Column('admin_action_notes', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('service_memo', schema=None) as batch_op:
        batch_op.drop_column('admin_action_notes')
