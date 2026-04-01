<!--
SYNC IMPACT REPORT
==================
Version change: [TEMPLATE] → 1.0.0 (initial ratification)
Modified principles: N/A (first-time fill from template)
Added sections:
  - Core Principles (I–V)
  - Quality Standards
  - Development Workflow
  - Governance
Removed sections: None
Templates requiring updates:
  - ✅ .specify/templates/plan-template.md — Constitution Check gates align with principles below
  - ✅ .specify/templates/spec-template.md — no changes required; structure already compatible
  - ✅ .specify/templates/tasks-template.md — task phases align with modular, test-first approach
Deferred TODOs: None
-->

# Meeting Agent Constitution

## Core Principles

### I. Modular & Clean Code (NON-NEGOTIABLE)

Every unit of code MUST have a single, clearly stated purpose.
Modules, classes, and functions MUST be self-contained, independently testable, and free of
hidden side-effects. God classes, deeply nested logic, and tangled cross-module dependencies
are prohibited. Each new component MUST clearly justify its existence and boundary.

**Rationale**: The meeting agent domain involves multiple concerns (transcription, summarization,
scheduling, action-item extraction). Keeping each concern in its own clean module prevents
accretion of complexity and makes the system safe to extend.

### II. Single Responsibility

Every module, service, and agent tool MUST own exactly one concern.
If a description requires the word "and" to cover what a component does, it MUST be split.
Shared utilities are permitted only when the abstraction is used in three or more distinct
places and is genuinely general-purpose.

**Rationale**: Supports Principle I — modularity is unenforceable without strict responsibility
boundaries.

### III. Test-First

Tests MUST be written before implementation begins. Each test MUST fail before the code that
makes it pass is written. The Red-Green-Refactor cycle is strictly enforced.
Integration tests are required for all agent-to-agent communication and external API calls.

**Rationale**: Meeting agent workflows span LLM calls, audio/text pipelines, and external
calendars/APIs. Untested integration paths are the primary source of production failures in
this domain.

### IV. Agent Composability

Every agent tool and pipeline stage MUST be independently invocable, accept well-defined
inputs, and produce well-defined outputs. No tool may depend on implicit shared global state.
Text-based I/O (structured JSON + human-readable) is the standard protocol between components.

**Rationale**: Composable tools can be tested, replaced, and reused individually — a
prerequisite for maintaining a clean modular architecture as the agent grows.

### V. Simplicity First (YAGNI)

The simplest solution that satisfies the current requirement MUST be implemented first.
Abstractions, generalization, and architectural patterns MUST NOT be added speculatively.
Every deviation from the simplest path MUST be documented in the plan's Complexity Tracking
table with a concrete justification.

**Rationale**: Premature complexity is the leading cause of code that violates Principle I.
Simplicity is the precondition for modularity.

## Quality Standards

All code MUST pass linting and formatting checks before merge (no exceptions).
Type annotations are REQUIRED for all public interfaces.
Code review MUST verify compliance with Principles I–V before approval.
Performance-sensitive paths MUST include a benchmark or latency target in the task definition.
Security-sensitive paths (API keys, user data, audio/transcript storage) MUST undergo a
targeted security review — no broad "security hardening" tasks without a specific threat
identified.

## Development Workflow

Feature branches MUST be created from `main` and merged via pull request.
Each PR MUST reference the spec and plan documents for the feature.
Commits SHOULD be atomic — one logical change per commit.
The Complexity Tracking table in the plan MUST be filled in whenever a Constitution Check
gate is violated; the PR cannot be merged without it.
Tasks MUST be organized by user story (per `.specify/templates/tasks-template.md`) to enable
independent delivery of each story.

## Governance

This constitution supersedes all informal practices and prior verbal agreements.
Amendments require: (1) a written proposal describing the change and rationale, (2) a version
bump following semantic versioning (MAJOR for principle removal/redefinition, MINOR for
additions, PATCH for clarifications), and (3) an updated Sync Impact Report in this file.
All PRs and code reviews MUST verify compliance with the principles above.
Complexity MUST be justified in writing — "it felt cleaner" is not a justification.
Use `.specify/memory/constitution.md` (this file) as the authoritative runtime governance
reference.

**Version**: 1.0.0 | **Ratified**: 2026-03-30 | **Last Amended**: 2026-03-30
