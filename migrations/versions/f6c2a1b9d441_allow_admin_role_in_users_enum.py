"""Allow admin role in users.user_type

Revision ID: f6c2a1b9d441
Revises: e5b8c3d7a114
Create Date: 2026-02-27 15:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'f6c2a1b9d441'
down_revision = 'e5b8c3d7a114'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE users
        MODIFY COLUMN user_type ENUM('technician','complaint_locker','other','admin')
        DEFAULT 'other'
        """
    )


def downgrade():
    op.execute("UPDATE users SET user_type='other' WHERE user_type='admin'")
    op.execute(
        """
        ALTER TABLE users
        MODIFY COLUMN user_type ENUM('technician','complaint_locker','other')
        DEFAULT 'other'
        """
    )
