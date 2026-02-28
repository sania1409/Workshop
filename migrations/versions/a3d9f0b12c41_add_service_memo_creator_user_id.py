"""Add service memo creator user id

Revision ID: a3d9f0b12c41
Revises: 1b8654a635d7
Create Date: 2026-02-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3d9f0b12c41'
down_revision = '1b8654a635d7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('service_memo', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_by_user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_service_memo_created_by_user',
            'users',
            ['created_by_user_id'],
            ['user_id']
        )

    # Backfill owner from legacy username mapping.
    op.execute(
        """
        UPDATE service_memo sm
        JOIN users u ON sm.user_name = u.username
        SET sm.created_by_user_id = u.user_id
        WHERE sm.created_by_user_id IS NULL
        """
    )


def downgrade():
    with op.batch_alter_table('service_memo', schema=None) as batch_op:
        batch_op.drop_constraint('fk_service_memo_created_by_user', type_='foreignkey')
        batch_op.drop_column('created_by_user_id')
