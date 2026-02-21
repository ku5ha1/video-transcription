#!/bin/bash
# Build script with Docker BuildKit enabled for cache mounts

set -e

echo "Building Docker image with BuildKit cache mounts..."
echo "This will cache pip packages and Hugging Face models for faster rebuilds"
echo ""

# Enable BuildKit
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Build with docker compose
docker compose build "$@"

echo ""
echo "Build complete! Cache is stored in Docker BuildKit cache."
echo "Subsequent builds will be much faster."
echo ""
echo "To rebuild from scratch (clearing cache):"
echo "  docker builder prune"
echo ""
echo "To see cache usage:"
echo "  docker system df"
