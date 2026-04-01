import json
import logging
import sys
from datetime import UTC, datetime


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload)


def configure_logging(log_level: str = "INFO") -> None:
    """Call once at application startup to configure root logger with JSON output."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JSONFormatter())

    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root.handlers.clear()
    root.addHandler(handler)

    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. configure_logging() must have been called first."""
    return logging.getLogger(name)
