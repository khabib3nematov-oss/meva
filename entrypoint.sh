#!/bin/sh
set -eu

: "${DATABASE_URL:?DATABASE_URL must be set before running migrations}"

echo "Running database migrations..."
alembic upgrade head

echo "Seeding branches..."
python seed_branches.py

echo "Database migrations and seeding complete. Starting bot..."
exec python -m app.main
