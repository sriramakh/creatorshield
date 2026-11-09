"""Store file sizes above 2 GB (uploads go up to 5 GB)."""

import sqlalchemy as sa
from alembic import op

revision = "0b7c5d2e9f31"
down_revision = "f012a123abcd"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("analyses", "size_bytes", type_=sa.BigInteger(), existing_type=sa.Integer())


def downgrade():
    op.alter_column("analyses", "size_bytes", type_=sa.Integer(), existing_type=sa.BigInteger())
