"""
Engineer cross-system identity normalizer.

Two-pass resolution against the canonical Engineer store:
  Pass 1 — exact email match (highest confidence)
  Pass 2 — rapidfuzz token_sort_ratio ≥ 90 on display name

Returns a mapping {jira_username: engineer_id} for every resolved identity.
Unresolved identities are printed to stdout for manual review.

Standalone CLI:
    python -m src.ingestion.normalizer --resolve-engineers
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass

from rapidfuzz.fuzz import token_sort_ratio
from sqlalchemy.ext.asyncio import AsyncSession

from src.logging_config import configure_logging, get_logger
from src.storage.database import AsyncSessionLocal
from src.storage.models import Engineer
from src.storage.repository import EngineerRepository

logger = get_logger(__name__)

_FUZZY_THRESHOLD = 90  # token_sort_ratio ≥ 90 is a match


@dataclass
class JiraIdentity:
    """Raw identity data extracted from a Jira issue."""

    username: str  # Jira account ID / username
    display_name: str
    email: str | None = None


async def resolve_engineer(
    session: AsyncSession,
    identity: JiraIdentity,
    all_engineers: list[Engineer],
) -> Engineer:
    """
    Resolve a JiraIdentity to an Engineer record, creating one if needed.

    Mutates `all_engineers` in-place so subsequent calls in the same batch
    can match against newly created records.
    """
    # ------------------------------------------------------------------ #
    # Pass 1 — exact email match
    # ------------------------------------------------------------------ #
    if identity.email:
        engineer = await EngineerRepository.get_by_email(session, identity.email)
        if engineer:
            _update_aliases(session, engineer, identity)
            return engineer

    # ------------------------------------------------------------------ #
    # Pass 2 — fuzzy display-name match
    # ------------------------------------------------------------------ #
    best_score = 0
    best_match: Engineer | None = None
    for eng in all_engineers:
        score = token_sort_ratio(identity.display_name.lower(), eng.display_name.lower())
        if score >= _FUZZY_THRESHOLD and score > best_score:
            best_score = score
            best_match = eng

    if best_match:
        logger.debug(
            "Fuzzy matched %r → %r (score=%d)", identity.display_name, best_match.display_name, best_score
        )
        _update_aliases(session, best_match, identity)
        return best_match

    # ------------------------------------------------------------------ #
    # No match — create new canonical Engineer
    # ------------------------------------------------------------------ #
    new_names: list[str] = []
    if identity.display_name:
        new_names.append(identity.display_name)

    engineer = await EngineerRepository.create(
        session,
        display_name=identity.display_name,
        email=identity.email,
        jira_username=identity.username,
        copilot_display_names=new_names,
    )
    all_engineers.append(engineer)
    logger.info("Created new Engineer %r (id=%s)", identity.display_name, engineer.id)
    return engineer


def _update_aliases(session: AsyncSession, engineer: Engineer, identity: JiraIdentity) -> None:
    """Patch missing aliases on an existing Engineer record (no flush — caller commits)."""
    changed = False
    if not engineer.jira_username and identity.username:
        engineer.jira_username = identity.username
        changed = True
    if not engineer.email and identity.email:
        engineer.email = identity.email
        changed = True
    existing_names: list[str] = list(engineer.copilot_display_names or [])
    if identity.display_name and identity.display_name not in existing_names:
        existing_names.append(identity.display_name)
        engineer.copilot_display_names = existing_names
        changed = True
    if changed:
        session.add(engineer)


async def normalize_engineers(
    session: AsyncSession,
    identities: list[JiraIdentity],
) -> dict[str, str]:
    """
    Batch-resolve a list of JiraIdentity objects.

    Returns {jira_username: engineer_id}.
    Prints unresolved identities (those created fresh) so operators can
    verify the new entries are correct.
    """
    all_engineers = await EngineerRepository.list_all(session)
    result: dict[str, str] = {}

    for identity in identities:
        engineer = await resolve_engineer(session, identity, all_engineers)
        result[identity.username] = engineer.id

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


async def _cli_resolve() -> None:
    """Print all Engineer records and flag any that lack email or jira_username."""
    async with AsyncSessionLocal() as session:
        engineers = await EngineerRepository.list_all(session)
    if not engineers:
        print("No engineers in the database yet. Run a sync first.")
        return
    unresolved: list[Engineer] = []
    print(f"{'Display Name':<35} {'Email':<35} {'Jira Username':<25}")
    print("-" * 95)
    for eng in engineers:
        email = eng.email or "[MISSING]"
        jira = eng.jira_username or "[MISSING]"
        print(f"{eng.display_name:<35} {email:<35} {jira:<25}")
        if not eng.email or not eng.jira_username:
            unresolved.append(eng)
    print()
    if unresolved:
        print(f"⚠  {len(unresolved)} engineer(s) have incomplete cross-system identity data:")
        for eng in unresolved:
            fields = []
            if not eng.email:
                fields.append("email")
            if not eng.jira_username:
                fields.append("jira_username")
            print(f"  • {eng.display_name!r} (id={eng.id}) — missing: {', '.join(fields)}")
        print("\nUpdate these via direct DB edit or re-run sync after fixing the source system data.")
    else:
        print("All engineers have complete cross-system identity data.")


def main() -> int:
    configure_logging("INFO")
    parser = argparse.ArgumentParser(description="Engineer identity resolution utilities.")
    parser.add_argument(
        "--resolve-engineers",
        action="store_true",
        help="List all canonical Engineer records and flag incomplete identities.",
    )
    args = parser.parse_args()

    if args.resolve_engineers:
        asyncio.run(_cli_resolve())
    else:
        parser.print_help()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
