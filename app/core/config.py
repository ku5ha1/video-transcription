import os
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # App settings
    app_name: str = "Video Transcription API"
    debug: bool = False
    
    # Model settings
    device: str = "cpu"
    model_size: str = "tiny"
    
    # File settings
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    upload_dir: str = "uploads"
    output_dir: str = "output"
    
    # Emotion/Tone candidates (matching legacy config)
    candidate_emotions: List[str] = ["joy", "anger", "sadness", "excitement", "calmness", "interest", "confusion"]
    candidate_tones: List[str] = ["enthusiastic", "confident", "inquisitive", "hesitant", "professional", "sarcastic", "neutral"]
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # Allow extra fields from .env

settings = Settings()