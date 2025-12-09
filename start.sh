#!/bin/sh
set -e

# Run database migrations (continue even if they fail, in case tables already exist)
python3 -m alembic upgrade head || true

# Get PORT from environment variable (Railway sets this)
PORT=${PORT:-8000}

# Start the application
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"

