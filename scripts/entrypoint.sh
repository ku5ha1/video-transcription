#!/bin/bash
set -e

echo "Waiting for PostgreSQL to be ready..."
until PGPASSWORD=password psql -h "postgres" -U "postgres" -d "transcription_db" -c '\q' 2>/dev/null; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done

echo "PostgreSQL is up - running migrations"
alembic upgrade head

# Download models at container startup (only if not already downloaded)
# Use flock to prevent race condition between app and celery containers
echo "Checking and downloading AI models..."
LOCK_FILE="/tmp/model_download.lock"
(
    flock -n 200 || { echo "Another container is downloading models. Waiting..."; flock -w 300 200 || { echo "Timeout waiting for model download"; exit 1; } }
    
    # Double-check after acquiring lock by verifying model artifacts, not just directories
    if [ ! -d "/app/models/emotion/models--Dpngtm--wav2vec2-emotion-recognition" ] || \
       [ ! -d "/app/models/tone/models--cross-encoder--nli-deberta-v3-small" ] || \
       [ ! -f "/app/models/sherpa/sherpa-onnx-pyannote-segmentation-3-0/model.onnx" ] || \
       [ ! -f "/app/models/sherpa/nemo_en_titanet_small.onnx" ]; then
        echo "Models not found, downloading..."
        python /app/scripts/download_models.py --hf-token "${HUGGING_FACE_TOKEN:-}"
    else
        echo "Models already exist, skipping download"
    fi
) 200>"$LOCK_FILE"

echo "Migrations completed - starting application"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
