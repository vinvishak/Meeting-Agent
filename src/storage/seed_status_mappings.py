"""
CLI utility to seed StatusMapping records.

Maps raw Jira status names to the normalised lifecycle stages used by the
classifier (open / in_progress / review / done / blocked).

Usage:
    python -m src.storage.seed_status_mappings \\
        --board-id BOARD-1 \\
        --mapping "To Do=open" \\
        --mapping "In Progress=in_progress" \\
        --mapping "In Review=review" \\
        --mapping "Done=done" \\
        --mapping "Blocked=blocked"

Each --mapping value is a "Raw Jira Status=normalized_status" pair.
Valid normalized values: open, in_progress, review, done, blocked.
"""

import argparse
import asyncio
import sys

from src.logging_config import configure_logging, get_logger
from src.storage.database import AsyncSessionLocal
from src.storage.models import NormalizedStatus
from src.storage.repository import StatusMappingRepository

logger = get_logger(__name__)

_VALID_NORMALIZED = {s.value for s in NormalizedStatus}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed Jira status mappings into the database.")
    parser.add_argument(
        "--board-id",
        required=True,
        help="Jira board ID (e.g. BOARD-1)",
    )
    parser.add_argument(
        "--mapping",
        action="append",
        dest="mappings",
        metavar="RAW=NORMALIZED",
        default=[],
        help="Mapping in 'Raw Jira Status=normalized_status' format. Repeatable.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without touching the database.",
    )
    return parser.parse_args()


def _parse_mapping(raw_arg: str) -> tuple[str, str]:
    """Split 'Raw Status=normalized' into a (raw, normalized) pair."""
    if "=" not in raw_arg:
        raise ValueError(f"Mapping must be in 'RAW=NORMALIZED' format, got: {raw_arg!r}")
    idx = raw_arg.index("=")
    raw_status = raw_arg[:idx].strip()
    normalized = raw_arg[idx + 1 :].strip().lower()
    if not raw_status:
        raise ValueError(f"Raw status name is empty in mapping: {raw_arg!r}")
    if normalized not in _VALID_NORMALIZED:
        raise ValueError(
            f"Invalid normalized status {normalized!r}. Valid values: {sorted(_VALID_NORMALIZED)}"
        )
    return raw_status, normalized


async def _seed(board_id: str, pairs: list[tuple[str, str]], dry_run: bool) -> None:
    if dry_run:
        logger.info("Dry-run mode — no database writes.")
        for raw, normalized in pairs:
            print(f"  [DRY RUN] board={board_id!r}  {raw!r} → {normalized!r}")
        return

    async with AsyncSessionLocal() as session:
        written = 0
        for raw_status, normalized in pairs:
            mapping = await StatusMappingRepository.upsert(session, board_id, raw_status, normalized)
            logger.info("Upserted mapping: board=%r  %r → %r  (id=%s)", board_id, raw_status, normalized, mapping.id)
            written += 1
        await session.commit()
    print(f"Done. Wrote {written} status mapping(s) for board {board_id!r}.")


def main() -> int:
    configure_logging("INFO")
    args = _parse_args()

    if not args.mappings:
        print("No --mapping arguments provided. Nothing to do.", file=sys.stderr)
        return 1

    pairs: list[tuple[str, str]] = []
    for raw_arg in args.mappings:
        try:
            pairs.append(_parse_mapping(raw_arg))
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    asyncio.run(_seed(args.board_id, pairs, args.dry_run))
    return 0


if __name__ == "__main__":
    sys.exit(main())
