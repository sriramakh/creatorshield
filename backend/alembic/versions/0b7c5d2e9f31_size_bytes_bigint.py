"""Store file sizes above 2 GB (uploads go up to 5 GB)."""

import sqlalchemy as sa

from alembic import op

revision = "0b7c5d2e9f31"
down_revision = "f012a123abcd"
branch_labels = None
depends_on = None

INT_MAX = 2**31 - 1


def upgrade():
    op.alter_column("analyses", "size_bytes", type_=sa.BigInteger(), existing_type=sa.Integer())


def downgrade():
    # A 32-bit column cannot hold sizes above 2 GiB. Refuse instead of failing
    # half-way or truncating: delete or shrink those analyses first.
    if not context_is_offline():
        too_big = (
            op.get_bind()
            .execute(sa.text("SELECT count(*) FROM analyses WHERE size_bytes > :m"), {"m": INT_MAX})
            .scalar()
        )
        if too_big:
            raise RuntimeError(
                f"Cannot downgrade: {too_big} analyses have size_bytes above {INT_MAX} "
                "(files over 2 GiB). Delete them first; this downgrade does not truncate data."
            )
    op.alter_column("analyses", "size_bytes", type_=sa.Integer(), existing_type=sa.BigInteger())


def context_is_offline() -> bool:
    from alembic import context

    return context.is_offline_mode()
