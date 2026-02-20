import os
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # App settings
    app_name: str = "Video Transcription API"
    debug: bool = False
    log_level: str = "INFO"
    
    # Model settings
    device: str = "cpu"
    model_size: str = "tiny"  # Deprecated, use whisper_model_id
    
    # Whisper settings
    whisper_model_id: str = "deepdml/faster-whisper-large-v3-turbo-ct2"
    whisper_compute_type: str = "int8"
    whisper_model_cache_dir: str = "/app/models/whisper"
    whisper_language: str = ""  # Auto-detect if empty
    
    # File settings
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    allowed_video_extensions: List[str] = [".mp4", ".avi", ".mov", ".mkv", ".webm"]
    upload_dir: str = "uploads"
    output_dir: str = "output"
    
    # Database
    database_url: str = "postgresql://postgres:password@localhost:5432/transcription_db"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    
    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    
    # Emotion/Tone candidates (matching legacy config)
    candidate_emotions: List[str] = ["joy", "anger", "sadness", "excitement", "calmness", "interest", "confusion"]
    candidate_tones: List[str] = ["enthusiastic", "confident", "inquisitive", "hesitant", "professional", "sarcastic", "neutral"]
    
    # Sherpa-ONNX Diarization settings
    sherpa_base_dir: str = "sherpa-onnx"
    sherpa_model_dir: str = os.getenv("SHERPA_MODEL_DIR", "sherpa-onnx")
    sherpa_clustering_threshold: float = 0.8
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # Allow extra fields from .env

settings = Settings()