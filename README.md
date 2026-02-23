# Multimodal Video Intelligence & Semantic RAG Pipeline

A privacy-preserving pipeline for deep video analysis and semantic retrieval. This system synchronizes multiple local ML models to transform raw video into a structured, searchable knowledge base, featuring a custom semantic reconstruction layer for high-fidelity RAG.

## Technical Philosophy

Unlike standard RAG implementations that treat transcripts as flat text, this system utilizes a **Semantic Buffer Aggregator**. This ensures that word-level timestamps are reconstructed into coherent thoughts, maintaining the temporal and logical integrity of video context before vectorization.

## Tech Stack

**Inference Engine**: faster-whisper (large-v3-turbo), Pyannote 3.1 (Sherpa ONNX), Wav2Vec2, DeBERTa-v3

**Orchestration**: FastAPI, Celery, Redis

**Storage**: Qdrant (Vector Search), PostgreSQL (Metadata), MinIO (Object Storage)

**Optimization**: CTranslate2 (int8 quantization), Redis-backed caching, SHA-256 file deduplication

**LLM**: Gemini 2.5 Flash (RAG + Chat)

**DevOps**: Docker Compose, GitHub Actions (CI), Ruff (Linting), Bandit (Security)

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              User Interface                              │
│                         (Web UI / API Client)                           │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         FastAPI Gateway                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │ Rate Limiter │  │ Auth (JWT)   │  │ File Hash    │                 │
│  │ (SlowAPI)    │  │              │  │ (SHA-256)    │                 │
│  └──────────────┘  └──────────────┘  └──────────────┘                 │
└────────────────────────────┬────────────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │ PostgreSQL  │  │   MinIO     │  │   Redis     │
    │ (Metadata)  │  │  (Videos)   │  │  (Cache)    │
    └─────────────┘  └─────────────┘  └──────┬──────┘
                                              │
                                              ▼
                                    ┌─────────────────┐
                                    │  Celery Worker  │
                                    │   (Async Task)  │
                                    └────────┬────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
                    ▼                        ▼                        ▼
          ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
          │ Whisper (ASR)    │    │ Pyannote         │    │ Wav2Vec2 +       │
          │ + Word Timestamps│    │ (Diarization)    │    │ DeBERTa (NLP)    │
          └──────────────────┘    └──────────────────┘    └──────────────────┘
                    │                        │                        │
                    └────────────────────────┼────────────────────────┘
                                             │
                                             ▼
                                  ┌─────────────────────┐
                                  │ Semantic Aggregator │
                                  │ (Reconstruct Logic) │
                                  └──────────┬──────────┘
                                             │
                                             ▼
                                    ┌─────────────────┐
                                    │ Qdrant Vector DB│
                                    │ (Embeddings)    │
                                    └────────┬────────┘
                                             │
                                             ▼
                                    ┌─────────────────┐
                                    │ Gemini 2.5 Flash│
                                    │ (RAG + Chat)    │
                                    └─────────────────┘
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.10+

### Installation

```bash
# Clone repository
git clone https://github.com/ku5ha1/video-transcription/
cd video-transcription

# Configure environment
cp .env.example .env
# Edit .env with your credentials (GEMINI_API_KEY, JWT_SECRET_KEY)

# Start services
docker compose up -d

# Check logs
docker logs -f video-transcription-app-1
```

The application will be available at:
- Web UI: http://localhost:8000
- API Docs: http://localhost:8000/docs
- MinIO Console: http://localhost:9001

## API Documentation

### Authentication

All endpoints require JWT authentication via Bearer token or session cookie.

**Register User**
```http
POST /api/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "secure_password"
}
```

**Login**
```http
POST /api/auth/login
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=secure_password
```

### Video Processing

**Upload Video**
```http
POST /api/transcription/transcribe
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: <video.mp4>
```

Response:
```json
{
  "task_id": "abc-123-def",
  "status": "submitted",
  "message": "Video transcription task submitted"
}
```

**Check Task Status**
```http
GET /api/transcription/status/{task_id}
```

Response:
```json
{
  "task_id": "abc-123-def",
  "status": "SUCCESS",
  "result": {
    "video_id": "uuid-here",
    "segments_count": 42
  }
}
```

**List Videos**
```http
GET /api/transcription/videos?page=1&page_size=20
Authorization: Bearer <token>
```

**Get Video Details with Transcript**
```http
GET /api/transcription/videos/{video_id}
Authorization: Bearer <token>
```

Response:
```json
{
  "id": "uuid",
  "filename": "video.mp4",
  "status": "completed",
  "duration": 120.5,
  "segments": [
    {
      "start_time": 0.0,
      "end_time": 5.2,
      "speaker_label": "SPEAKER_00",
      "text": "Hello, this is a test.",
      "audio_emotion": "neutral",
      "text_tone": "informative"
    }
  ]
}
```

### Semantic Search & Chat

**Chat with Video**
```http
POST /api/web/chat/{video_id}
Content-Type: application/json

{
  "query": "What did the speaker say about AI?"
}
```

Response:
```json
{
  "answer": "Based on the 42 segments analyzed, the speaker defines AI as a transformative force, specifically highlighting...",
  "source_segments": [
    {
      "text": "AI is transforming industries",
      "timestamp": "[02:15]",
      "speaker": "SPEAKER_00",
      "score": 0.89
    }
  ]
}
```

### Rate Limits

- Global: 20 requests/minute
- Upload endpoints: 2 requests/minute
- Transcription: 2 requests/minute

## Resource Optimization & Hardware Awareness

The system is architected for constrained environments (e.g., 20GB RAM CPU setup):

**Model Quantization**: Employs int8 weights to reduce memory footprint by ~70% without significant accuracy loss.

**Memory Management**: Implemented singleton model loading and persistent worker contexts to prevent RAM thrashing.

**Task Serialization**: Uses specific Redis queues to isolate heavy inference tasks, preventing CPU contention and ensuring system stability.

**Caching Strategy**:
- Transcript responses: 1-hour TTL
- LLM chat responses: 2-hour TTL
- File deduplication: SHA-256 hash-based

## Development

### Running Tests

```bash
# Inside container
docker exec -it video-transcription-app-1 bash
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=app --cov-report=term
```
Note: Integration tests are configured for mocked environments to prevent high-memory model loading during CI/CD.

### Code Quality

```bash
# Linting
ruff check app/ tests/

# Formatting
ruff format app/ tests/

# Security scan
bandit -r app/
```

### Database Migrations

```bash
# Create migration
docker exec -it video-transcription-app-1 alembic revision --autogenerate -m "description"

# Apply migrations
docker exec -it video-transcription-app-1 alembic upgrade head
```

## Scalability & vLLM Integration

To transition from a local deployment to a high-throughput enterprise environment:

**Inference Decoupling**: Replace local Whisper/LLM instances with a vLLM serving cluster. vLLM's PagedAttention and continuous batching would allow the system to handle significantly higher concurrent video streams on GPU hardware.

**Unified VLMs**: Serving Vision Language Models (e.g., Qwen2-VL) via vLLM to extract visual temporal features (OCR, action recognition) directly into the metadata layer.

## Future Enhancements

**Indic Language Support**: Integration of fine-tuned ASR models (e.g., IndicWhisper) for Hindi, Tamil, and Bengali, including support for code-mixed (Hinglish) speech.

**Phonetic Alignment**: Implementing phonetic search for Indic scripts to improve retrieval accuracy across diverse regional accents.

**Knowledge Graph RAG**: Transitioning from flat vector similarity to Knowledge Graphs (Neo4j) to map complex entities and relationships across massive video libraries.

## Project Structure

```
.
├── app/
│   ├── api/              # FastAPI routes
│   ├── core/             # Config, database, security
│   ├── models/           # SQLAlchemy models
│   ├── services/         # Business logic (transcription, chat, etc.)
│   ├── utils/            # Helpers (semantic aggregator, caching)
│   └── templates/        # HTML templates
├── alembic/              # Database migrations
├── tests/                # Test suite
├── scripts/              # Utility scripts
├── .github/workflows/    # CI/CD pipelines
├── docker-compose.yml    # Service orchestration
└── requirements.txt      # Python dependencies
```