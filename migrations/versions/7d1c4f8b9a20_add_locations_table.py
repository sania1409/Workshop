"""Add locations table

Revision ID: 7d1c4f8b9a20
Revises: 9c3d7e1a4b22
Create Date: 2026-03-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7d1c4f8b9a20"
down_revision = "9c3d7e1a4b22"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.execute(
        """
        INSERT IGNORE INTO locations (name)
        VALUES
            ('head_office'),
            ('station'),
            ('workshop'),
            ('other')
        """
    )


def downgrade():
    op.drop_table("locations")
