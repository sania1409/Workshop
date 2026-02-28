"""Add technician availability and complaint assignment metadata

Revision ID: b7f1d2e9a8c3
Revises: a3d9f0b12c41
Create Date: 2026-02-27 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7f1d2e9a8c3'
down_revision = 'a3d9f0b12c41'
branch_labels = None
depends_on = None


availability_enum = sa.Enum('available', 'busy', 'offline', name='technicianprofile_availability_status')


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tech_columns = {col["name"] for col in inspector.get_columns("technician_profile")}
    complaint_columns = {col["name"] for col in inspector.get_columns("complaints")}

    with op.batch_alter_table('technician_profile', schema=None) as batch_op:
        if 'availability_status' not in tech_columns:
            batch_op.add_column(sa.Column('availability_status', availability_enum, nullable=True))
        if 'max_active_jobs' not in tech_columns:
            batch_op.add_column(sa.Column('max_active_jobs', sa.Integer(), nullable=True))

    op.execute("UPDATE technician_profile SET availability_status='available' WHERE availability_status IS NULL")
    op.execute("UPDATE technician_profile SET max_active_jobs=1 WHERE max_active_jobs IS NULL")

    with op.batch_alter_table('technician_profile', schema=None) as batch_op:
        batch_op.alter_column(
            'availability_status',
            existing_type=availability_enum,
            nullable=False,
        )
        batch_op.alter_column(
            'max_active_jobs',
            existing_type=sa.Integer(),
            nullable=False,
        )

    with op.batch_alter_table('complaints', schema=None) as batch_op:
        if 'assigned_at' not in complaint_columns:
            batch_op.add_column(sa.Column('assigned_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('complaints', schema=None) as batch_op:
        batch_op.drop_column('assigned_at')

    with op.batch_alter_table('technician_profile', schema=None) as batch_op:
        batch_op.drop_column('max_active_jobs')
        batch_op.drop_column('availability_status')
