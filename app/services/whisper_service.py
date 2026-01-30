from faster_whisper import WhisperModel
from app.core.config import settings

class WhisperService:
    """Service for audio transcription using Faster-Whisper"""
    
    def __init__(self):
        print(f"Loading Transcription Model: faster-whisper ({settings.model_size})")
        self.model = WhisperModel(
            settings.model_size, 
            device=settings.device, 
            compute_type="int8"
        )
    
    def transcribe_audio(self, audio_path: str):
        """Transcribe audio file and return segments"""
        print("Starting Transcription...")
        segments, _ = self.model.transcribe(audio_path, beam_size=5)
        return segments