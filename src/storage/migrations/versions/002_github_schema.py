"""GitHub integration schema — 4 new tables

Revision ID: 002_github_schema
Revises: 001_initial_schema
Create Date: 2026-05-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002_github_schema"
down_revision: str | None = "001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # github_repos
    # -----------------------------------------------------------------------
    op.create_table(
        "github_repos",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("org", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(511), nullable=False),
        sa.Column("default_branch", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("full_name"),
    )
    op.create_index("ix_github_repos_org", "github_repos", ["org"])

    # -----------------------------------------------------------------------
    # github_commits
    # -----------------------------------------------------------------------
    op.create_table(
        "github_commits",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("repo_id", sa.String(36), nullable=False),
        sa.Column("sha", sa.String(40), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("author_login", sa.String(255), nullable=True),
        sa.Column("author_name", sa.String(255), nullable=True),
        sa.Column("author_email", sa.String(255), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("branch", sa.String(255), nullable=True),
        sa.Column("url", sa.String(1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repo_id"], ["github_repos.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sha"),
    )
    op.create_index("ix_github_commits_repo_id", "github_commits", ["repo_id"])
    op.create_index("ix_github_commits_committed_at", "github_commits", ["committed_at"])

    # -----------------------------------------------------------------------
    # github_pull_requests
    # -----------------------------------------------------------------------
    op.create_table(
        "github_pull_requests",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("repo_id", sa.String(36), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("author_login", sa.String(255), nullable=True),
        sa.Column("head_branch", sa.String(255), nullable=True),
        sa.Column("base_branch", sa.String(255), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("url", sa.String(1024), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repo_id"], ["github_repos.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repo_id", "pr_number", name="uq_github_pr_repo_number"),
    )
    op.create_index("ix_github_pull_requests_repo_id", "github_pull_requests", ["repo_id"])
    op.create_index("ix_github_pull_requests_state", "github_pull_requests", ["state"])
    op.create_index("ix_github_pull_requests_opened_at", "github_pull_requests", ["opened_at"])

    # -----------------------------------------------------------------------
    # github_jira_links
    # -----------------------------------------------------------------------
    op.create_table(
        "github_jira_links",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("source_type", sa.String(10), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=True),
        sa.Column("pr_id", sa.String(36), nullable=True),
        sa.Column("jira_key", sa.String(50), nullable=False),
        sa.Column("ticket_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["pr_id"], ["github_pull_requests.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_github_jira_links_commit_sha", "github_jira_links", ["commit_sha"])
    op.create_index("ix_github_jira_links_pr_id", "github_jira_links", ["pr_id"])
    op.create_index("ix_github_jira_links_jira_key", "github_jira_links", ["jira_key"])
    op.create_index("ix_github_jira_links_ticket_id", "github_jira_links", ["ticket_id"])


def downgrade() -> None:
    op.drop_table("github_jira_links")
    op.drop_table("github_pull_requests")
    op.drop_table("github_commits")
    op.drop_table("github_repos")
