# syntax=docker/dockerfile:1.4
# Python 3.10
FROM python:3.10-slim AS app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wget \
    bzip2 \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Set Hugging Face cache directory
ENV HF_HOME=/root/.cache/huggingface

# Copy requirements and install Python dependencies with cache mount
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Copy model download script (models downloaded at runtime, not build time)
COPY scripts/download_models.py /app/scripts/download_models.py

# Copy application code
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Copy entrypoint script
COPY scripts/entrypoint.sh /app/scripts/entrypoint.sh
RUN chmod +x /app/scripts/entrypoint.sh

# Set Python path
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run entrypoint script (migrations + app)
CMD ["/app/scripts/entrypoint.sh"]

# Celery stage - inherits from app stage
FROM app AS celery
CMD ["celery", "-A", "app.core.celery", "worker", "--loglevel=info"]