"""Extend update_suggestions to support commit-sourced suggestions

Revision ID: 003_commit_suggestion_source
Revises: 002_github_schema
Create Date: 2026-05-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003_commit_suggestion_source"
down_revision: str | None = "002_github_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Make transcript_mention_id nullable (commits have no transcript mention)
    with op.batch_alter_table("update_suggestions") as batch_op:
        batch_op.alter_column("transcript_mention_id", existing_type=sa.String(36), nullable=True)
        batch_op.add_column(sa.Column("source_type", sa.String(20), nullable=False, server_default="transcript"))
        batch_op.add_column(sa.Column("commit_sha", sa.String(40), nullable=True))
        batch_op.create_index("ix_update_suggestions_commit_sha", ["commit_sha"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("update_suggestions") as batch_op:
        batch_op.drop_index("ix_update_suggestions_commit_sha")
        batch_op.drop_column("commit_sha")
        batch_op.drop_column("source_type")
        batch_op.alter_column("transcript_mention_id", existing_type=sa.String(36), nullable=False)
