"""Initial schema — all 9 entities

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-03-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # engineers
    # -----------------------------------------------------------------------
    op.create_table(
        "engineers",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("jira_username", sa.String(255), nullable=True),
        sa.Column("copilot_display_names", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("jira_username"),
    )

    # -----------------------------------------------------------------------
    # sprints
    # -----------------------------------------------------------------------
    op.create_table(
        "sprints",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("jira_sprint_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("board_id", sa.String(255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("committed_points", sa.Float(), nullable=True),
        sa.Column("completed_points", sa.Float(), nullable=True),
        sa.Column("velocity", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jira_sprint_id"),
    )
    op.create_index("ix_sprints_board_id", "sprints", ["board_id"])

    # -----------------------------------------------------------------------
    # status_mappings
    # -----------------------------------------------------------------------
    op.create_table(
        "status_mappings",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("board_id", sa.String(255), nullable=False),
        sa.Column("jira_status_name", sa.String(255), nullable=False),
        sa.Column("normalized_status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("board_id", "jira_status_name", name="uq_status_mapping_board_status"),
    )

    # -----------------------------------------------------------------------
    # tickets  (depends on engineers, sprints)
    # -----------------------------------------------------------------------
    op.create_table(
        "tickets",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("jira_id", sa.String(50), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assignee_id", sa.String(36), nullable=True),
        sa.Column("sprint_id", sa.String(36), nullable=True),
        sa.Column("jira_status", sa.String(100), nullable=False),
        sa.Column("normalized_status", sa.String(20), nullable=False),
        sa.Column("priority", sa.String(50), nullable=True),
        sa.Column("story_points", sa.Float(), nullable=True),
        sa.Column("labels", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("linked_issue_ids", sa.JSON(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("inferred_status", sa.String(30), nullable=False),
        sa.Column("inferred_status_reason", sa.Text(), nullable=False),
        sa.Column("inferred_status_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assignee_id"], ["engineers.id"]),
        sa.ForeignKeyConstraint(["sprint_id"], ["sprints.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jira_id"),
    )
    op.create_index("ix_tickets_assignee_id", "tickets", ["assignee_id"])
    op.create_index("ix_tickets_sprint_id", "tickets", ["sprint_id"])
    op.create_index("ix_tickets_inferred_status", "tickets", ["inferred_status"])

    # -----------------------------------------------------------------------
    # ticket_snapshots  (depends on tickets, engineers, sprints)
    # -----------------------------------------------------------------------
    op.create_table(
        "ticket_snapshots",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("ticket_id", sa.String(36), nullable=False),
        sa.Column("jira_status", sa.String(100), nullable=False),
        sa.Column("normalized_status", sa.String(20), nullable=False),
        sa.Column("assignee_id", sa.String(36), nullable=True),
        sa.Column("sprint_id", sa.String(36), nullable=True),
        sa.Column("story_points", sa.Float(), nullable=True),
        sa.Column("inferred_status", sa.String(30), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.ForeignKeyConstraint(["assignee_id"], ["engineers.id"]),
        sa.ForeignKeyConstraint(["sprint_id"], ["sprints.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_snapshots_ticket_id", "ticket_snapshots", ["ticket_id"])
    op.create_index("ix_ticket_snapshots_snapshot_at", "ticket_snapshots", ["snapshot_at"])

    # -----------------------------------------------------------------------
    # transcripts
    # -----------------------------------------------------------------------
    op.create_table(
        "transcripts",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("copilot_meeting_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("participants", sa.JSON(), nullable=False),
        sa.Column("raw_transcript", sa.Text(), nullable=False),
        sa.Column("copilot_summary", sa.Text(), nullable=True),
        sa.Column("action_items", sa.JSON(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("copilot_meeting_id"),
    )
    op.create_index("ix_transcripts_started_at", "transcripts", ["started_at"])

    # -----------------------------------------------------------------------
    # transcript_mentions  (depends on transcripts, tickets, engineers)
    # -----------------------------------------------------------------------
    op.create_table(
        "transcript_mentions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("transcript_id", sa.String(36), nullable=False),
        sa.Column("ticket_id", sa.String(36), nullable=True),
        sa.Column("speaker_name", sa.String(255), nullable=False),
        sa.Column("speaker_engineer_id", sa.String(36), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("excerpt_timestamp_seconds", sa.Integer(), nullable=True),
        sa.Column("match_type", sa.String(20), nullable=False),
        sa.Column("match_confidence", sa.Float(), nullable=False),
        sa.Column("mention_intent", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["transcript_id"], ["transcripts.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.ForeignKeyConstraint(["speaker_engineer_id"], ["engineers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transcript_mentions_transcript_id", "transcript_mentions", ["transcript_id"])
    op.create_index("ix_transcript_mentions_ticket_id", "transcript_mentions", ["ticket_id"])

    # -----------------------------------------------------------------------
    # update_suggestions  (depends on transcript_mentions, tickets, engineers)
    # -----------------------------------------------------------------------
    op.create_table(
        "update_suggestions",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("transcript_mention_id", sa.String(36), nullable=False),
        sa.Column("ticket_id", sa.String(36), nullable=False),
        sa.Column("update_type", sa.String(30), nullable=False),
        sa.Column("proposed_value", sa.JSON(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("confidence_tier", sa.String(10), nullable=False),
        sa.Column("approval_state", sa.String(20), nullable=False),
        sa.Column("conflict_flag", sa.Boolean(), nullable=False),
        sa.Column("conflict_details", sa.Text(), nullable=True),
        sa.Column("reviewed_by_id", sa.String(36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["transcript_mention_id"], ["transcript_mentions.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["engineers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_update_suggestions_ticket_id", "update_suggestions", ["ticket_id"])
    op.create_index("ix_update_suggestions_approval_state", "update_suggestions", ["approval_state"])

    # -----------------------------------------------------------------------
    # audit_entries  (depends on tickets, update_suggestions, transcript_mentions, engineers)
    # -----------------------------------------------------------------------
    op.create_table(
        "audit_entries",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("ticket_id", sa.String(36), nullable=True),
        sa.Column("update_suggestion_id", sa.String(36), nullable=True),
        sa.Column("transcript_mention_id", sa.String(36), nullable=True),
        sa.Column("actor_engineer_id", sa.String(36), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("signal_inputs", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.ForeignKeyConstraint(["update_suggestion_id"], ["update_suggestions.id"]),
        sa.ForeignKeyConstraint(["transcript_mention_id"], ["transcript_mentions.id"]),
        sa.ForeignKeyConstraint(["actor_engineer_id"], ["engineers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_entries_event_type", "audit_entries", ["event_type"])
    op.create_index("ix_audit_entries_ticket_id", "audit_entries", ["ticket_id"])
    op.create_index("ix_audit_entries_created_at", "audit_entries", ["created_at"])


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("audit_entries")
    op.drop_table("update_suggestions")
    op.drop_table("transcript_mentions")
    op.drop_table("transcripts")
    op.drop_table("ticket_snapshots")
    op.drop_table("tickets")
    op.drop_table("status_mappings")
    op.drop_table("sprints")
    op.drop_table("engineers")
