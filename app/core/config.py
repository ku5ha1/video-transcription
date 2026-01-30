import os
from pydantic_settings import BaseSettings

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
    
    # Emotion/Tone candidates
    candidate_emotions: list = ["joy", "anger", "sadness", "excitement", "calmness", "interest", "confusion"]
    candidate_tones: list = ["enthusiastic", "confident", "inquisitive", "hesitant", "professional", "sarcastic", "neutral"]
    
    class Config:
        env_file = ".env"

settings = Settings()