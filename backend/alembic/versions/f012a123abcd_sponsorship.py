"""Store declared sponsorship context for uploads and imports."""

from alembic import op
import sqlalchemy as sa

revision = "f012a123abcd"
down_revision = "e091a123abcd"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("analyses", sa.Column("sponsorship", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("analyses", "sponsorship")
