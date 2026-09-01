#!/bin/sh
set -e

# 12-factor: DATABASE_URL is injected via compose environment.
# Run migrations on every container start so schema and code stay in sync.
echo "Running database migrations..."
# alembic upgrade head — explicit config ensures correct path inside container
alembic -c alembic.ini upgrade head

echo "Starting gunicorn..."
exec gunicorn --bind 0.0.0.0:8000 --workers 2 app.wsgi:app
