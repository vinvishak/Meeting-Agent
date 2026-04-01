"""
Maintenance worker — 12-month rolling retention purge (T046).

Deletes TicketSnapshot and Transcript records older than 12 months.
AuditEntry records are never purged (per data-model.md).

Registered as a nightly APScheduler job via scheduler.py.

Standalone CLI:
    python -m src.workers.maintenance_worker --run-once
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta

from src.logging_config import configure_logging, get_logger
from src.storage.database import AsyncSessionLocal
from src.storage.repository import SnapshotRepository, TranscriptRepository

logger = get_logger(__name__)

_RETENTION_MONTHS = 12


async def run_retention_purge() -> None:
    """Delete snapshots and transcripts older than 12 months."""
    cutoff = datetime.now(UTC) - timedelta(days=_RETENTION_MONTHS * 30)

    async with AsyncSessionLocal() as session:
        snapshot_count = await SnapshotRepository.delete_older_than(session, cutoff)
        transcript_count = await TranscriptRepository.delete_older_than(session, cutoff)
        await session.commit()

    logger.info(
        "Retention purge complete: deleted %d snapshot(s) and %d transcript(s) older than %s",
        snapshot_count,
        transcript_count,
        cutoff.date().isoformat(),
    )


def main() -> int:
    configure_logging("INFO")
    parser = argparse.ArgumentParser(description="Data retention maintenance worker.")
    parser.add_argument("--run-once", action="store_true", help="Run one purge cycle and exit.")
    args = parser.parse_args()
    if args.run_once:
        asyncio.run(run_retention_purge())
        return 0
    print("Use --run-once or run via the scheduler.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
