"""
SQLAlchemy 2.x ORM models for all 9 entities.

All string-based enum columns store the enum value directly; Python enum
classes are defined here and used throughout the application for type safety.
"""

import uuid
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(UTC)


def _uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enum definitions
# ---------------------------------------------------------------------------


class NormalizedStatus(StrEnum):
    open = "open"
    in_progress = "in_progress"
    review = "review"
    done = "done"
    blocked = "blocked"


class InferredStatus(StrEnum):
    officially_in_progress = "officially_in_progress"
    likely_in_progress = "likely_in_progress"
    blocked = "blocked"
    stale = "stale"
    completed_not_updated = "completed_not_updated"


class SprintState(StrEnum):
    future = "future"
    active = "active"
    closed = "closed"


class MatchType(StrEnum):
    exact_id = "exact_id"
    semantic = "semantic"
    unresolved = "unresolved"


class MentionIntent(StrEnum):
    progress_update = "progress_update"
    blocker = "blocker"
    completion = "completion"
    ownership_change = "ownership_change"
    eta_change = "eta_change"
    dependency = "dependency"
    future_intent = "future_intent"
    ambiguous = "ambiguous"


class UpdateType(StrEnum):
    status_transition = "status_transition"
    add_comment = "add_comment"
    update_assignee = "update_assignee"
    set_blocked = "set_blocked"
    update_due_date = "update_due_date"


class ConfidenceTier(StrEnum):
    high = "high"
    medium = "medium"
    low = "low"


class ApprovalState(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    auto_applied = "auto_applied"


class AuditEventType(StrEnum):
    status_inferred = "status_inferred"
    suggestion_created = "suggestion_created"
    suggestion_approved = "suggestion_approved"
    suggestion_rejected = "suggestion_rejected"
    suggestion_auto_applied = "suggestion_auto_applied"
    sync_completed = "sync_completed"
    sync_failed = "sync_failed"


# ---------------------------------------------------------------------------
# Entity: Engineer
# ---------------------------------------------------------------------------


class Engineer(Base):
    """Canonical cross-system identity for a person in Jira or Copilot data."""

    __tablename__ = "engineers"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=_uuid)
    display_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(sa.String(255), unique=True, nullable=True)
    jira_username: Mapped[str | None] = mapped_column(sa.String(255), unique=True, nullable=True)
    copilot_display_names: Mapped[list] = mapped_column(sa.JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

    # Relationships
    tickets: Mapped[list["Ticket"]] = relationship(
        "Ticket", back_populates="assignee", foreign_keys="Ticket.assignee_id", lazy="select"
    )
    transcript_mentions_as_speaker: Mapped[list["TranscriptMention"]] = relationship(
        "TranscriptMention",
        back_populates="speaker_engineer",
        foreign_keys="TranscriptMention.speaker_engineer_id",
        lazy="select",
    )
    reviewed_suggestions: Mapped[list["UpdateSuggestion"]] = relationship(
        "UpdateSuggestion",
        back_populates="reviewed_by",
        foreign_keys="UpdateSuggestion.reviewed_by_id",
        lazy="select",
    )
    audit_entries_as_actor: Mapped[list["AuditEntry"]] = relationship(
        "AuditEntry",
        back_populates="actor_engineer",
        foreign_keys="AuditEntry.actor_engineer_id",
        lazy="select",
    )


# ---------------------------------------------------------------------------
# Entity: Sprint
# ---------------------------------------------------------------------------


class Sprint(Base):
    """A Jira sprint or time-boxed reporting period."""

    __tablename__ = "sprints"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=_uuid)
    jira_sprint_id: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    board_id: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    start_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    state: Mapped[str] = mapped_column(sa.String(20), nullable=False)  # SprintState value
    committed_points: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    completed_points: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    velocity: Mapped[float | None] = mapped_column(sa.Float, nullable=True)

    tickets: Mapped[list["Ticket"]] = relationship("Ticket", back_populates="sprint", lazy="select")


# ---------------------------------------------------------------------------
# Entity: StatusMapping
# ---------------------------------------------------------------------------


class StatusMapping(Base):
    """Configurable rule: raw Jira status name → normalized lifecycle stage."""

    __tablename__ = "status_mappings"
    __table_args__ = (
        sa.UniqueConstraint("board_id", "jira_status_name", name="uq_status_mapping_board_status"),
    )

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=_uuid)
    board_id: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    jira_status_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    normalized_status: Mapped[str] = mapped_column(sa.String(20), nullable=False)  # NormalizedStatus value
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=_now)


# ---------------------------------------------------------------------------
# Entity: Ticket
# ---------------------------------------------------------------------------


class Ticket(Base):
    """Current state of a Jira work item. History is in TicketSnapshot."""

    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=_uuid)
    jira_id: Mapped[str] = mapped_column(sa.String(50), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    assignee_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("engineers.id"), nullable=True, index=True
    )
    sprint_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("sprints.id"), nullable=True, index=True
    )
    jira_status: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    normalized_status: Mapped[str] = mapped_column(sa.String(20), nullable=False)  # NormalizedStatus value
    priority: Mapped[str | None] = mapped_column(sa.String(50), nullable=True)
    story_points: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    labels: Mapped[list] = mapped_column(sa.JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    due_date: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    linked_issue_ids: Mapped[list] = mapped_column(sa.JSON, nullable=False, default=list)
    last_synced_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=_now)
    inferred_status: Mapped[str] = mapped_column(
        sa.String(30), nullable=False, default=InferredStatus.stale.value, index=True
    )
    inferred_status_reason: Mapped[str] = mapped_column(sa.Text, nullable=False, default="")
    inferred_status_updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now
    )

    # Relationships
    assignee: Mapped[Optional["Engineer"]] = relationship(
        "Engineer", back_populates="tickets", foreign_keys=[assignee_id], lazy="select"
    )
    sprint: Mapped[Optional["Sprint"]] = relationship("Sprint", back_populates="tickets", lazy="select")
    snapshots: Mapped[list["TicketSnapshot"]] = relationship(
        "TicketSnapshot", back_populates="ticket", lazy="select"
    )
    transcript_mentions: Mapped[list["TranscriptMention"]] = relationship(
        "TranscriptMention", back_populates="ticket", lazy="select"
    )
    update_suggestions: Mapped[list["UpdateSuggestion"]] = relationship(
        "UpdateSuggestion", back_populates="ticket", lazy="select"
    )
    audit_entries: Mapped[list["AuditEntry"]] = relationship(
        "AuditEntry", back_populates="ticket", foreign_keys="AuditEntry.ticket_id", lazy="select"
    )


# ---------------------------------------------------------------------------
# Entity: TicketSnapshot
# ---------------------------------------------------------------------------


class TicketSnapshot(Base):
    """Immutable historical record of a ticket's state. Retained for 12 months."""

    __tablename__ = "ticket_snapshots"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=_uuid)
    ticket_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("tickets.id"), nullable=False, index=True
    )
    jira_status: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    normalized_status: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    assignee_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("engineers.id"), nullable=True
    )
    sprint_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("sprints.id"), nullable=True
    )
    story_points: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    inferred_status: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    snapshot_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now, index=True
    )

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="snapshots", lazy="select")


# ---------------------------------------------------------------------------
# Entity: Transcript
# ---------------------------------------------------------------------------


class Transcript(Base):
    """A meeting record ingested from the Copilot MCP Server. Retained for 12 months."""

    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=_uuid)
    copilot_meeting_id: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(sa.String(500), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, index=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    participants: Mapped[list] = mapped_column(sa.JSON, nullable=False, default=list)
    raw_transcript: Mapped[str] = mapped_column(sa.Text, nullable=False)
    copilot_summary: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    action_items: Mapped[list] = mapped_column(sa.JSON, nullable=False, default=list)
    processed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now
    )

    mentions: Mapped[list["TranscriptMention"]] = relationship(
        "TranscriptMention", back_populates="transcript", lazy="select"
    )


# ---------------------------------------------------------------------------
# Entity: TranscriptMention
# ---------------------------------------------------------------------------


class TranscriptMention(Base):
    """A reference to a Jira ticket found within a transcript."""

    __tablename__ = "transcript_mentions"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=_uuid)
    transcript_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("transcripts.id"), nullable=False, index=True
    )
    ticket_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("tickets.id"), nullable=True, index=True
    )
    speaker_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    speaker_engineer_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("engineers.id"), nullable=True
    )
    excerpt: Mapped[str] = mapped_column(sa.Text, nullable=False)
    excerpt_timestamp_seconds: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    match_type: Mapped[str] = mapped_column(sa.String(20), nullable=False)  # MatchType value
    match_confidence: Mapped[float] = mapped_column(sa.Float, nullable=False)
    mention_intent: Mapped[str] = mapped_column(sa.String(30), nullable=False)  # MentionIntent value
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=_now)

    # Relationships
    transcript: Mapped["Transcript"] = relationship("Transcript", back_populates="mentions", lazy="select")
    ticket: Mapped[Optional["Ticket"]] = relationship(
        "Ticket", back_populates="transcript_mentions", lazy="select"
    )
    speaker_engineer: Mapped[Optional["Engineer"]] = relationship(
        "Engineer",
        back_populates="transcript_mentions_as_speaker",
        foreign_keys=[speaker_engineer_id],
        lazy="select",
    )
    update_suggestion: Mapped[Optional["UpdateSuggestion"]] = relationship(
        "UpdateSuggestion", back_populates="transcript_mention", uselist=False, lazy="select"
    )
    audit_entries: Mapped[list["AuditEntry"]] = relationship(
        "AuditEntry",
        back_populates="transcript_mention",
        foreign_keys="AuditEntry.transcript_mention_id",
        lazy="select",
    )


# ---------------------------------------------------------------------------
# Entity: UpdateSuggestion
# ---------------------------------------------------------------------------


class UpdateSuggestion(Base):
    """A proposed Jira change derived from a TranscriptMention."""

    __tablename__ = "update_suggestions"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=_uuid)
    transcript_mention_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("transcript_mentions.id"), nullable=False
    )
    ticket_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("tickets.id"), nullable=False, index=True
    )
    update_type: Mapped[str] = mapped_column(sa.String(30), nullable=False)  # UpdateType value
    proposed_value: Mapped[dict] = mapped_column(sa.JSON, nullable=False)
    confidence_score: Mapped[float] = mapped_column(sa.Float, nullable=False)
    confidence_tier: Mapped[str] = mapped_column(sa.String(10), nullable=False)  # ConfidenceTier value
    approval_state: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, default=ApprovalState.pending.value, index=True
    )
    conflict_flag: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    conflict_details: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    reviewed_by_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("engineers.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=_now)

    # Relationships
    transcript_mention: Mapped["TranscriptMention"] = relationship(
        "TranscriptMention", back_populates="update_suggestion", lazy="select"
    )
    ticket: Mapped["Ticket"] = relationship(
        "Ticket", back_populates="update_suggestions", lazy="select"
    )
    reviewed_by: Mapped[Optional["Engineer"]] = relationship(
        "Engineer",
        back_populates="reviewed_suggestions",
        foreign_keys=[reviewed_by_id],
        lazy="select",
    )
    audit_entries: Mapped[list["AuditEntry"]] = relationship(
        "AuditEntry",
        back_populates="update_suggestion",
        foreign_keys="AuditEntry.update_suggestion_id",
        lazy="select",
    )


# ---------------------------------------------------------------------------
# Entity: AuditEntry
# ---------------------------------------------------------------------------


class AuditEntry(Base):
    """Immutable log of any AI-driven classification, suggestion, or applied change. Never purged."""

    __tablename__ = "audit_entries"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=_uuid)
    event_type: Mapped[str] = mapped_column(sa.String(30), nullable=False, index=True)  # AuditEventType value
    ticket_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("tickets.id"), nullable=True, index=True
    )
    update_suggestion_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("update_suggestions.id"), nullable=True
    )
    transcript_mention_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("transcript_mentions.id"), nullable=True
    )
    actor_engineer_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("engineers.id"), nullable=True
    )
    reasoning: Mapped[str] = mapped_column(sa.Text, nullable=False)
    signal_inputs: Mapped[dict] = mapped_column(sa.JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now, index=True
    )

    # Relationships
    ticket: Mapped[Optional["Ticket"]] = relationship(
        "Ticket", back_populates="audit_entries", foreign_keys=[ticket_id], lazy="select"
    )
    update_suggestion: Mapped[Optional["UpdateSuggestion"]] = relationship(
        "UpdateSuggestion",
        back_populates="audit_entries",
        foreign_keys=[update_suggestion_id],
        lazy="select",
    )
    transcript_mention: Mapped[Optional["TranscriptMention"]] = relationship(
        "TranscriptMention",
        back_populates="audit_entries",
        foreign_keys=[transcript_mention_id],
        lazy="select",
    )
    actor_engineer: Mapped[Optional["Engineer"]] = relationship(
        "Engineer",
        back_populates="audit_entries_as_actor",
        foreign_keys=[actor_engineer_id],
        lazy="select",
    )


# ---------------------------------------------------------------------------
# Entity: GitHubRepo
# ---------------------------------------------------------------------------


class GitHubRepo(Base):
    """A GitHub repository tracked under the configured org."""

    __tablename__ = "github_repos"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=_uuid)
    org: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(sa.String(511), unique=True, nullable=False)
    default_branch: Mapped[str] = mapped_column(sa.String(100), nullable=False, default="main")
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=_now)

    commits: Mapped[list["GitHubCommit"]] = relationship(
        "GitHubCommit", back_populates="repo", lazy="select"
    )
    pull_requests: Mapped[list["GitHubPullRequest"]] = relationship(
        "GitHubPullRequest", back_populates="repo", lazy="select"
    )


# ---------------------------------------------------------------------------
# Entity: GitHubCommit
# ---------------------------------------------------------------------------


class GitHubCommit(Base):
    """A git commit fetched from GitHub. Deduplicated by SHA."""

    __tablename__ = "github_commits"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=_uuid)
    repo_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("github_repos.id"), nullable=False, index=True
    )
    sha: Mapped[str] = mapped_column(sa.String(40), unique=True, nullable=False)
    message: Mapped[str] = mapped_column(sa.Text, nullable=False)
    author_login: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    author_name: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    author_email: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    committed_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, index=True)
    branch: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    url: Mapped[str | None] = mapped_column(sa.String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=_now)

    repo: Mapped["GitHubRepo"] = relationship("GitHubRepo", back_populates="commits", lazy="select")
    jira_links: Mapped[list["GitHubJiraLink"]] = relationship(
        "GitHubJiraLink",
        back_populates="commit",
        foreign_keys="GitHubJiraLink.commit_sha",
        primaryjoin="GitHubCommit.sha == foreign(GitHubJiraLink.commit_sha)",
        lazy="select",
    )


# ---------------------------------------------------------------------------
# Entity: GitHubPullRequest
# ---------------------------------------------------------------------------


class GitHubPullRequest(Base):
    """A GitHub pull request. State is updated on each sync."""

    __tablename__ = "github_pull_requests"
    __table_args__ = (
        sa.UniqueConstraint("repo_id", "pr_number", name="uq_github_pr_repo_number"),
    )

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=_uuid)
    repo_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("github_repos.id"), nullable=False, index=True
    )
    pr_number: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    title: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    body: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    state: Mapped[str] = mapped_column(sa.String(20), nullable=False)  # "open" | "closed" | "merged"
    author_login: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    head_branch: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    base_branch: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    merged_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    url: Mapped[str | None] = mapped_column(sa.String(1024), nullable=True)
    last_synced_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=_now)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=_now)

    repo: Mapped["GitHubRepo"] = relationship("GitHubRepo", back_populates="pull_requests", lazy="select")
    jira_links: Mapped[list["GitHubJiraLink"]] = relationship(
        "GitHubJiraLink", back_populates="pr", foreign_keys="GitHubJiraLink.pr_id", lazy="select"
    )


# ---------------------------------------------------------------------------
# Entity: GitHubJiraLink
# ---------------------------------------------------------------------------


class GitHubJiraLink(Base):
    """Association between a GitHub artifact (commit or PR) and a Jira ticket key."""

    __tablename__ = "github_jira_links"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=_uuid)
    source_type: Mapped[str] = mapped_column(sa.String(10), nullable=False)  # "commit" | "pr"
    commit_sha: Mapped[str | None] = mapped_column(sa.String(40), nullable=True, index=True)
    pr_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("github_pull_requests.id"), nullable=True, index=True
    )
    jira_key: Mapped[str] = mapped_column(sa.String(50), nullable=False, index=True)
    ticket_id: Mapped[str | None] = mapped_column(
        sa.String(36), sa.ForeignKey("tickets.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=_now)

    pr: Mapped[Optional["GitHubPullRequest"]] = relationship(
        "GitHubPullRequest", back_populates="jira_links", foreign_keys=[pr_id], lazy="select"
    )
    commit: Mapped[Optional["GitHubCommit"]] = relationship(
        "GitHubCommit",
        back_populates="jira_links",
        foreign_keys=[commit_sha],
        primaryjoin="GitHubJiraLink.commit_sha == GitHubCommit.sha",
        lazy="select",
    )
    ticket: Mapped[Optional["Ticket"]] = relationship(
        "Ticket", foreign_keys=[ticket_id], lazy="select"
    )
