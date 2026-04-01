"""
APScheduler job registration for the Jira sync worker.

Two modes:
  • Standalone process (production): BlockingScheduler — runs until SIGTERM.
  • Dev / embedded (main.py): start_scheduler_thread() — BackgroundScheduler
    in a daemon thread so the process exits cleanly when uvicorn stops.

Usage (standalone):
    python -m src.workers.scheduler

Usage (embedded via main.py):
    from src.workers.scheduler import start_scheduler_thread
    thread = start_scheduler_thread()
"""

import asyncio
import signal
import sys
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler

from src.config import get_settings
from src.logging_config import configure_logging, get_logger
from src.workers.sync_worker import run_sync_cycle

logger = get_logger(__name__)


def _run_cycle_sync() -> None:
    """APScheduler job target — runs the async sync cycle in a fresh event loop."""
    try:
        asyncio.run(run_sync_cycle())
    except Exception as exc:
        logger.error("Scheduled sync cycle raised an unhandled exception: %s", exc, exc_info=True)


def _run_retention_purge() -> None:
    """APScheduler job target — runs the nightly retention purge."""
    from src.workers.maintenance_worker import run_retention_purge

    try:
        asyncio.run(run_retention_purge())
    except Exception as exc:
        logger.error("Retention purge raised an unhandled exception: %s", exc, exc_info=True)


# ---------------------------------------------------------------------------
# Embedded (daemon thread) scheduler — used by main.py
# ---------------------------------------------------------------------------


def start_scheduler_thread() -> threading.Thread:
    """
    Start a BackgroundScheduler in a daemon thread.

    The scheduler runs `run_sync_cycle` every `SYNC_INTERVAL_MINUTES` minutes.
    Returns the thread so the caller can log its identity.
    """
    settings = get_settings()
    interval = settings.sync_interval_minutes

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        _run_cycle_sync,
        trigger="interval",
        minutes=interval,
        id="jira_sync",
        name="Jira sync cycle",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_retention_purge,
        trigger="cron",
        hour=2,
        minute=0,
        id="retention_purge",
        name="12-month retention purge",
        max_instances=1,
    )

    def _run() -> None:
        scheduler.start()
        logger.info("Background sync scheduler started (interval=%dm)", interval)
        # The BackgroundScheduler keeps running in its own threads; this thread
        # just parks here so the daemon thread stays alive.
        scheduler.shutdown(wait=True)

    thread = threading.Thread(target=_run, daemon=True, name="sync-scheduler")
    thread.start()
    return thread


# ---------------------------------------------------------------------------
# Standalone (blocking) scheduler — production separate-process mode
# ---------------------------------------------------------------------------


def main() -> int:
    configure_logging("INFO")
    settings = get_settings()
    interval = settings.sync_interval_minutes

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        _run_cycle_sync,
        trigger="interval",
        minutes=interval,
        id="jira_sync",
        name="Jira sync cycle",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_retention_purge,
        trigger="cron",
        hour=2,
        minute=0,
        id="retention_purge",
        name="12-month retention purge",
        max_instances=1,
    )

    def _handle_sigterm(signum: int, frame: object) -> None:
        logger.info("Received SIGTERM — shutting down scheduler")
        scheduler.shutdown(wait=False)

    signal.signal(signal.SIGTERM, _handle_sigterm)

    logger.info("Sync scheduler starting (interval=%dm) — press Ctrl+C to stop", interval)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
