#!/bin/bash
set -e

echo "Waiting for PostgreSQL to be ready..."
until PGPASSWORD=password psql -h "postgres" -U "postgres" -d "transcription_db" -c '\q' 2>/dev/null; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done

echo "PostgreSQL is up - running migrations"
alembic upgrade head

echo "Migrations completed - starting application"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
