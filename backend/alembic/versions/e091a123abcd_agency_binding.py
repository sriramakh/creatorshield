"""Bind dedicated pilot databases to one agency."""

from alembic import op
import sqlalchemy as sa

revision = "e091a123abcd"
down_revision = "a892f48ed573"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agency_binding",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agency_id", sa.Text(), nullable=False),
        sa.CheckConstraint("id = 1", name="single_agency"),
    )


def downgrade():
    op.drop_table("agency_binding")
