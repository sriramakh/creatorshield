"""owner supplied media for cross-checked imports

Revision ID: c3e1a9b74d20
Revises: 49a32d39827e
Create Date: 2026-10-21 17:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3e1a9b74d20"
down_revision: Union[str, Sequence[str], None] = "49a32d39827e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "analyses",
        sa.Column(
            "owner_supplied_media",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("analyses", "owner_supplied_media")
