"""Add diagnosis notes to service memo

Revision ID: d2f4b7a91c8e
Revises: c1a9e4d5f702
Create Date: 2026-02-27 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd2f4b7a91c8e'
down_revision = 'c1a9e4d5f702'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('service_memo', schema=None) as batch_op:
        batch_op.add_column(sa.Column('diagnosis_notes', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('service_memo', schema=None) as batch_op:
        batch_op.drop_column('diagnosis_notes')
