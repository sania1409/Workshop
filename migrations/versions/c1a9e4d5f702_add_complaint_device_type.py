"""Add complaint device type

Revision ID: c1a9e4d5f702
Revises: b7f1d2e9a8c3
Create Date: 2026-02-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1a9e4d5f702'
down_revision = 'b7f1d2e9a8c3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('complaints', schema=None) as batch_op:
        batch_op.add_column(sa.Column('device_type', sa.String(length=50), nullable=True))

    op.execute("UPDATE complaints SET device_type='other' WHERE device_type IS NULL")

    with op.batch_alter_table('complaints', schema=None) as batch_op:
        batch_op.alter_column('device_type', existing_type=sa.String(length=50), nullable=False)


def downgrade():
    with op.batch_alter_table('complaints', schema=None) as batch_op:
        batch_op.drop_column('device_type')
