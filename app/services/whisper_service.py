from faster_whisper import WhisperModel
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("services.whisper")


class WhisperService:
    """Service for audio transcription using Faster-Whisper"""

    def __init__(self):
        logger.info(f"Loading Whisper Model: {settings.whisper_model_id}")
        self.model = WhisperModel(
            settings.whisper_model_id,
            device=settings.device,
            compute_type=settings.whisper_compute_type,
            download_root=settings.whisper_model_cache_dir,
        )
        logger.info("Whisper model loaded successfully")

    def transcribe_audio(self, audio_path: str):
        """Transcribe audio file and return segments with word-level timestamps"""
        logger.info(f"Starting transcription for: {audio_path}")
        segments, info = self.model.transcribe(
            audio_path,
            beam_size=5,
            word_timestamps=True,
            language=settings.whisper_language if settings.whisper_language else None,
        )
        logger.info(f"Transcription completed. Detected language: {info.language}")
        return segments
