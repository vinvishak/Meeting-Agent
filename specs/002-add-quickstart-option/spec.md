# Feature Specification: Add Quickstart Option

**Feature Branch**: `002-add-quickstart-option`  
**Created**: 2026-04-01  
**Status**: Draft  
**Input**: User description: "Please add a quickstart option"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - First-Time Setup via Quickstart Command (Priority: P1)

A new user clones the repository and runs a single quickstart command that interactively guides them through environment configuration, database initialization, and validation — without needing to read the full quickstart guide.

**Why this priority**: The primary pain point for new users is the multi-step manual setup. A single entry point that automates or walks through each step delivers the most immediate value.

**Independent Test**: Can be fully tested by running the quickstart command on a clean environment and verifying the agent starts successfully at the end.

**Acceptance Scenarios**:

1. **Given** a clean environment with no `.env` file, **When** the user runs the quickstart command, **Then** the system prompts for each required credential, validates them, writes `.env`, initializes the database, and confirms the agent is ready to start.
2. **Given** an existing `.env` file, **When** the user runs the quickstart command, **Then** the system detects existing configuration, shows current values (secrets masked), and asks whether to keep or overwrite each setting.
3. **Given** invalid credentials are entered, **When** the quickstart command attempts to validate connectivity, **Then** the system reports which connection failed with a clear error message and allows the user to re-enter credentials without restarting the entire process.

---

### User Story 2 - Non-Interactive Quickstart with Flags (Priority: P2)

A developer running in CI or scripted environments wants to run the quickstart non-interactively by providing all required values as flags or environment variables, with the command exiting 0 on success and non-zero on failure.

**Why this priority**: Enables automated testing, Docker entrypoints, and onboarding scripts without manual interaction.

**Independent Test**: Can be tested by running the quickstart command with all required flags in a script and checking the exit code and resulting side effects (`.env` created, DB migrated).

**Acceptance Scenarios**:

1. **Given** all required values are passed as flags, **When** the quickstart command runs non-interactively, **Then** it completes setup, prints a summary, and exits 0.
2. **Given** a required flag is missing in non-interactive mode, **When** the command runs, **Then** it exits non-zero with a message listing the missing values.

---

### User Story 3 - Quickstart Health Check for Existing Installations (Priority: P3)

An existing user who has already set up the agent runs the quickstart command to verify their current configuration is still valid (e.g., after a credential rotation or environment change).

**Why this priority**: Provides ongoing value beyond first-time setup by acting as a connectivity and configuration diagnostic.

**Independent Test**: Can be tested by running the quickstart command against an already-configured environment and verifying it reports status for each component without modifying anything.

**Acceptance Scenarios**:

1. **Given** a fully configured environment, **When** the user runs the quickstart command, **Then** it checks each connection (Jira MCP, Copilot MCP, Claude API, database) and reports pass/fail for each.
2. **Given** one connection is broken, **When** the health check runs, **Then** the broken component is flagged with a suggested fix while all other components show as healthy.

---

### Edge Cases

- What happens when the database already has migrations applied and the user runs quickstart again?
- How does the system handle a `.env` file with some but not all required variables?
- What if the Claude API key is valid but has no remaining quota?
- What happens if quickstart is run without the required Python version?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a single entry-point command that runs the full quickstart flow.
- **FR-002**: System MUST support interactive mode that prompts for each required configuration value with a description and example.
- **FR-003**: System MUST support non-interactive mode via command-line flags to allow scripted execution.
- **FR-004**: System MUST validate connectivity to each external service (Jira MCP, Copilot MCP, Claude API) before completing setup and report pass/fail results per service.
- **FR-005**: System MUST run database migrations automatically as part of the quickstart flow.
- **FR-006**: System MUST detect an existing `.env` file and offer to preserve, merge, or overwrite existing values.
- **FR-007**: System MUST display a summary of all configuration values (with secrets masked) before writing the `.env` file.
- **FR-008**: System MUST exit with a non-zero code on failure and a zero code on success.
- **FR-009**: System MUST allow the user to re-enter a single invalid value without restarting the entire flow.
- **FR-010**: System MUST print a final "ready to start" message with the exact command to launch the agent after successful setup.

### Key Entities

- **Configuration**: The set of required environment variables (MCP URLs, tokens, API key, database URL, thresholds) with descriptions, examples, and validation rules.
- **Connection Check Result**: Per-service result of a connectivity probe (service name, pass/fail, error message if failed).
- **Quickstart Session**: The in-progress state of a quickstart run (values collected so far, completed steps, interactive vs. non-interactive mode).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user with all credentials available can complete setup and have the agent running in under 5 minutes.
- **SC-002**: The quickstart command completes without errors on a clean environment given valid credentials.
- **SC-003**: Non-interactive mode exits with code 0 when all required flags are provided and code 1 when any are missing.
- **SC-004**: All connection validation results are reported before writing any configuration, allowing users to correct issues before finalizing setup.
- **SC-005**: The quickstart command is idempotent — running it multiple times on an already-configured environment does not corrupt state.

## Assumptions

- The quickstart targets macOS and Linux; Windows support is out of scope for v1.
- Users have already installed dependencies (`uv sync` or `pip install`) before running quickstart; dependency installation is not handled by the command.
- The quickstart validates connectivity but does not trigger a full data sync; the first sync still runs via the worker after startup.
- Secrets entered interactively are not echoed to the terminal.
- The `.env.example` file in the repository root is the canonical list of required variables and their descriptions.
