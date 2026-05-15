# Feature Specification: GitHub Commit to Jira Semantic Matching

**Feature Branch**: `011-commit-jira-semantic-match`
**Created**: 2026-05-15
**Status**: Draft
**Input**: User description: "GitHub commit to Jira semantic matching — when a GitHub commit is pushed and no explicit Jira ticket ID is found in the commit message, use AI to automatically find the most relevant open Jira ticket by comparing the commit message against all active ticket titles. If a match is found with sufficient confidence, queue a suggestion for the engineer to review and approve before anything in Jira is changed."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automatic Ticket Matching from Commit Message (Priority: P1)

An engineer pushes a commit with a plain English message like "Fixed the login button not responding on mobile." Without typing any ticket ID, the system automatically finds the most relevant open Jira ticket, and within the next sync cycle, a suggestion appears in the dashboard for the engineer to review.

**Why this priority**: This is the core value of the feature — eliminating the need for engineers to manually tag commits with Jira ticket IDs. Everything else depends on this matching working correctly.

**Independent Test**: Push a commit with a message that clearly describes work covered by an existing open Jira ticket (without including the ticket ID). Within one sync cycle, a suggestion linking that commit to the correct ticket should appear in the dashboard suggestion queue.

**Acceptance Scenarios**:

1. **Given** an open Jira ticket titled "Mobile login button unresponsive", **When** a commit with message "Fixed the login button not responding on mobile" is pushed, **Then** a suggestion linking the commit to that ticket appears in the review queue within the next sync cycle
2. **Given** a commit message that is clearly unrelated to any open ticket, **When** the system evaluates it, **Then** no suggestion is created and no Jira ticket is touched
3. **Given** a commit message that already contains an explicit Jira ticket ID (e.g. SCRUM-3), **When** the system processes it, **Then** the AI matching step is skipped entirely — the explicit ID is used directly

---

### User Story 2 - Review and Approve Suggestions (Priority: P2)

An engineer opens the dashboard suggestion queue, sees a proposed Jira ticket link generated from a commit, reviews it, and either approves it (which updates Jira) or rejects it (which discards it with no changes to Jira).

**Why this priority**: The matching step is only useful if engineers can act on the suggestions. Without the review flow, matched suggestions have no effect.

**Independent Test**: After a suggestion is created (from US1), open the dashboard suggestions view, approve one suggestion, and verify the corresponding Jira ticket is updated. Reject another and verify Jira is unchanged.

**Acceptance Scenarios**:

1. **Given** a pending suggestion in the queue, **When** the engineer clicks Approve, **Then** the linked Jira ticket is updated and the suggestion is marked as approved
2. **Given** a pending suggestion in the queue, **When** the engineer clicks Reject, **Then** nothing in Jira changes and the suggestion is marked as rejected
3. **Given** the suggestion queue, **When** it is viewed, **Then** each suggestion clearly shows the commit message, the matched ticket title, and the AI's confidence level so the engineer can make an informed decision

---

### User Story 3 - Low Confidence Commits Are Silently Skipped (Priority: P3)

When a commit message is too vague or ambiguous to match any Jira ticket with sufficient confidence, the system silently skips it rather than creating a low-quality suggestion that would waste the engineer's time.

**Why this priority**: Quality of suggestions matters more than volume. A noisy suggestion queue erodes trust and causes engineers to stop reviewing.

**Independent Test**: Push a commit with a generic message like "minor fix" or "update". Verify no suggestion is created in the queue.

**Acceptance Scenarios**:

1. **Given** a commit message with no clear relationship to any open ticket, **When** the AI evaluates it, **Then** no suggestion is created
2. **Given** a commit message that matches multiple tickets at similar confidence levels, **When** the AI evaluates it, **Then** no suggestion is created (ambiguous match treated as no match)

---

### Edge Cases

- What if the same commit message matches an already-closed or resolved Jira ticket? Only open/active tickets should be candidates for matching.
- What if there are no open Jira tickets at all? The matching step should complete immediately with no suggestions created.
- What if the AI service is temporarily unavailable? The commit should be recorded without a suggestion — no data should be lost.
- What if a commit is delivered twice (duplicate webhook)? Only one suggestion should ever be created per commit.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST automatically attempt to match every incoming commit that contains no explicit Jira ticket ID against all currently open Jira tickets
- **FR-002**: The system MUST only create a suggestion when the match confidence meets or exceeds the configured threshold (default: 75%)
- **FR-003**: The system MUST skip the AI matching step entirely when an explicit Jira ticket ID is already present in the commit message
- **FR-004**: Each suggestion MUST display the commit message, the matched ticket title and ID, and the confidence level so the engineer has enough context to decide
- **FR-005**: Approving a suggestion MUST result in a Jira ticket update; rejecting MUST leave Jira unchanged
- **FR-006**: The system MUST only match against open/active Jira tickets — closed or resolved tickets must be excluded
- **FR-007**: Duplicate commits MUST NOT produce duplicate suggestions
- **FR-008**: If the AI matching service is unavailable, the commit MUST still be recorded — the failure must not cause data loss

### Key Entities

- **Commit**: A GitHub commit with a SHA, message, author, timestamp, and repository — the source of the matching input
- **Suggestion**: A proposed link between a commit and a Jira ticket, with a confidence score and approval state (pending / approved / rejected)
- **Jira Ticket**: An active work item with an ID, title, and status — the target of the match

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 80% of commits whose messages clearly describe work covered by an open ticket produce a correct suggestion
- **SC-002**: Fewer than 10% of suggestions in the queue are false positives (wrong ticket matched)
- **SC-003**: Engineers spend less than 30 seconds reviewing and actioning each suggestion
- **SC-004**: Zero Jira tickets are modified without explicit engineer approval

## Assumptions

- Engineers write commit messages in plain English that describe the work done — very terse messages like "wip" or "fix" are expected to produce no suggestions
- Only open/in-progress Jira tickets are candidates for matching — the system already syncs ticket status from Jira
- The suggestion review queue already exists in the dashboard and can display commit-sourced suggestions alongside transcript-sourced ones
- A single commit maps to at most one Jira ticket suggestion — one-to-many matching is out of scope for this version
- The AI matching confidence threshold (75%) is configurable but defaults to 75%
