"""Markets, brand briefs, readiness verdict, workspace settings, review outcome stats.

Revision ID: a1c0de5f2b10
Revises: 0b7c5d2e9f31
"""

import sqlalchemy as sa

from alembic import op

revision = "a1c0de5f2b10"
down_revision = "0b7c5d2e9f31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analyses", sa.Column("markets", sa.JSON(), nullable=True))
    op.add_column("analyses", sa.Column("brief", sa.JSON(), nullable=True))
    op.add_column("analyses", sa.Column("brief_check", sa.JSON(), nullable=True))
    op.add_column("analyses", sa.Column("readiness_verdict", sa.String(16), nullable=True))
    op.create_table(
        "brand_briefs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("brand", sa.String(120), nullable=False),
        sa.Column("spec", sa.JSON(), nullable=False),
    )
    op.create_table(
        "workspace_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("default_platform", sa.String(32), nullable=False),
        sa.Column("default_markets", sa.JSON(), nullable=False),
        sa.Column("default_language", sa.String(8), nullable=False),
        sa.Column("onboarded", sa.Boolean(), nullable=False),
        sa.CheckConstraint("id = 1", name="single_workspace"),
    )
    op.create_table(
        "analysis_stats",
        sa.Column("analysis_id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("markets", sa.JSON(), nullable=False),
        sa.Column("client_label", sa.String(100), nullable=True),
        sa.Column("analysis_mode", sa.String(24), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column("risk_level", sa.String(16), nullable=True),
        sa.Column("verdict", sa.String(16), nullable=True),
        sa.Column("open_findings", sa.Integer(), nullable=False),
        sa.Column("severity_counts", sa.JSON(), nullable=False),
        sa.Column("group_counts", sa.JSON(), nullable=False),
    )
    op.create_index("ix_analysis_stats_created_at", "analysis_stats", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_analysis_stats_created_at", table_name="analysis_stats")
    op.drop_table("analysis_stats")
    op.drop_table("workspace_settings")
    op.drop_table("brand_briefs")
    op.drop_column("analyses", "readiness_verdict")
    op.drop_column("analyses", "brief_check")
    op.drop_column("analyses", "brief")
    op.drop_column("analyses", "markets")
