from typing import Optional, Dict, Any
from fastapi import HTTPException

class TranscriptionError(Exception):
    """Base exception for transcription-related errors"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

class VideoProcessingError(TranscriptionError):
    """Exception raised during video processing"""
    pass

class AudioExtractionError(TranscriptionError):
    """Exception raised during audio extraction"""
    pass

class TranscriptionModelError(TranscriptionError):
    """Exception raised during transcription"""
    pass

class SpeakerDiarizationError(TranscriptionError):
    """Exception raised during speaker diarization"""
    pass

class MetadataExtractionError(TranscriptionError):
    """Exception raised during metadata extraction"""
    pass

class FileValidationError(TranscriptionError):
    """Exception raised during file validation"""
    pass

def create_http_exception(error: TranscriptionError, status_code: int = 500) -> HTTPException:
    """Convert custom exception to HTTP exception"""
    return HTTPException(
        status_code=status_code,
        detail={
            "error": error.__class__.__name__,
            "message": error.message,
            "details": error.details
        }
    )