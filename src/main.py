"""
Application entry point.

Development (API + sync worker in one process):
    python -m src.main

Production (separate processes per quickstart.md §6):
    # Terminal 1 — API server:
    uvicorn src.api.app:app --host 0.0.0.0 --port 8000

    # Terminal 2 — Background sync worker:
    python -m src.workers.sync_worker
"""

import sys

import uvicorn

from src.api.app import create_app
from src.config import get_settings
from src.logging_config import configure_logging, get_logger


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = get_logger(__name__)

    app = create_app()

    # Start the background sync scheduler in a daemon thread so the process
    # exits cleanly when the API server stops.  The scheduler module is
    # implemented in Phase 3 (T020); this import is guarded so the API still
    # starts without it during earlier phases.
    try:
        from src.workers.scheduler import start_scheduler_thread

        scheduler_thread = start_scheduler_thread()
        logger.info("Sync scheduler started (thread id=%s)", scheduler_thread.ident)
    except ImportError:
        logger.info("Sync scheduler not yet available — API-only mode")

    logger.info("Starting API server on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level=settings.log_level.lower())


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# Allow: python -m src.main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(main() or 0)
