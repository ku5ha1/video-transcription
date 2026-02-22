#!/bin/bash

# Run Alembic migration for chat messages table
echo "Running chat messages migration..."

# Run migration inside the app container
docker-compose exec app alembic upgrade head

echo "Migration complete!"
