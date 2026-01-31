from fastapi import APIRouter, UploadFile, File, HTTPException
from app.models.transcription import TranscriptionResponse
from app.services.transcription_service import TranscriptionService
from app.core.exceptions import FileValidationError, create_http_exception
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("api.transcription")
router = APIRouter()
transcription_service = TranscriptionService()

def validate_file(file: UploadFile) -> None:
    """Validate uploaded file"""
    if not file.filename:
        raise FileValidationError("No filename provided")
    
    # Check file extension
    file_ext = "." + file.filename.split(".")[-1].lower()
    if file_ext not in settings.allowed_video_extensions:
        raise FileValidationError(
            f"Invalid file format: {file_ext}",
            details={"allowed_formats": settings.allowed_video_extensions}
        )
    
    # Check file size (if available)
    if hasattr(file, 'size') and file.size and file.size > settings.max_file_size:
        raise FileValidationError(
            f"File too large: {file.size} bytes",
            details={"max_size": settings.max_file_size}
        )

@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_video(file: UploadFile = File(...)):
    """
    Upload a video file and get transcription with emotion/tone analysis
    """
    logger.info("Transcription request received", extra={
        "extra_fields": {"filename": file.filename, "content_type": file.content_type}
    })
    
    try:
        # Validate file
        validate_file(file)
        logger.info("File validation passed", extra={"extra_fields": {"filename": file.filename}})
        
        # Process video
        result = await transcription_service.process_video(file)
        
        logger.info("Transcription completed successfully", extra={
            "extra_fields": {
                "filename": file.filename,
                "segments_count": result.total_segments,
                "processing_time": result.processing_time
            }
        })
        
        return result
        
    except FileValidationError as e:
        logger.error("File validation failed", extra={
            "extra_fields": {"filename": file.filename, "error": str(e)}
        })
        raise create_http_exception(e, 400)
        
    except Exception as e:
        logger.error("Transcription processing failed", extra={
            "extra_fields": {"filename": file.filename, "error": str(e)}
        }, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@router.get("/status/{task_id}")
async def get_transcription_status(task_id: str):
    """
    Get the status of a transcription task
    """
    logger.info("Status check requested", extra={"extra_fields": {"task_id": task_id}})
    # Placeholder for future async task tracking
    return {"task_id": task_id, "status": "completed"}