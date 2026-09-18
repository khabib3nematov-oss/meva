#!/bin/sh
set -eu

: "${DATABASE_URL:?DATABASE_URL must be set before running migrations}"

echo "Running database migrations..."
alembic upgrade head

echo "Database migrations complete. Starting bot..."
exec python -m app.main
