#!/usr/bin/env bash
set -e

echo "Running database migrations…"
uv run alembic upgrade head

echo "Starting server…"
exec uv run uvicorn src.api.app:create_app \
  --factory \
  --host 0.0.0.0 \
  --port "${PORT:-8000}"
