"""Add internal demand issue vouchers table

Revision ID: 9c3d7e1a4b22
Revises: f6c2a1b9d441
Create Date: 2026-03-06 18:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9c3d7e1a4b22"
down_revision = "f6c2a1b9d441"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "internal_demand_issue_vouchers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("complaint_id", sa.Integer(), nullable=False),
        sa.Column("item_description", sa.String(length=255), nullable=False),
        sa.Column("quantity_issued", sa.Integer(), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_by_admin_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["complaint_id"], ["complaints.id"]),
        sa.ForeignKeyConstraint(["created_by_admin_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("complaint_id"),
    )


def downgrade():
    op.drop_table("internal_demand_issue_vouchers")
