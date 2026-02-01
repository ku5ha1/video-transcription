from fastapi import APIRouter, UploadFile, File, HTTPException
from app.models.transcription import TranscriptionResponse
from app.models.task import TaskResponse, TaskStatusResponse
from app.services.transcription_service import TranscriptionService
from app.core.exceptions import FileValidationError, create_http_exception
from app.core.config import settings
from app.core.logging import get_logger
from app.core.celery import celery_app, process_video_task
from celery.result import AsyncResult
import tempfile
import os

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

@router.post("/transcribe", response_model=TaskResponse)
async def transcribe_video(file: UploadFile = File(...)):
    """
    Upload a video file and start asynchronous transcription processing
    """
    logger.info("Transcription request received", extra={
        "extra_fields": {"filename": file.filename, "content_type": file.content_type}
    })
    
    try:
        # Validate file
        validate_file(file)
        logger.info("File validation passed", extra={"extra_fields": {"filename": file.filename}})
        
        # Save uploaded file to shared directory
        os.makedirs("/tmp/shared", exist_ok=True)
        temp_video = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4', dir="/tmp/shared")
        content = await file.read()
        temp_video.write(content)
        temp_video.close()
        temp_video_path = temp_video.name
        
        logger.info("File saved temporarily", extra={
            "extra_fields": {"filename": file.filename, "temp_path": temp_video_path}
        })
        
        # Submit task to Celery
        task = process_video_task.delay(temp_video_path, file.filename)
        
        logger.info("Task submitted to Celery", extra={
            "extra_fields": {"filename": file.filename, "task_id": task.id}
        })
        
        return TaskResponse(
            task_id=task.id,
            status="submitted",
            message=f"Video transcription task submitted for {file.filename}"
        )
        
    except FileValidationError as e:
        logger.error("File validation failed", extra={
            "extra_fields": {"filename": file.filename, "error": str(e)}
        })
        raise create_http_exception(e, 400)
        
    except Exception as e:
        logger.error("Task submission failed", extra={
            "extra_fields": {"filename": file.filename, "error": str(e)}
        }, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Task submission failed: {str(e)}")

@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_transcription_status(task_id: str):
    """
    Get the status of a transcription task
    """
    logger.info("Status check requested", extra={"extra_fields": {"task_id": task_id}})
    
    try:
        result = AsyncResult(task_id, app=celery_app)
        
        response = TaskStatusResponse(
            task_id=task_id,
            status=result.status,
            result=result.result if result.ready() else None,
            meta=result.info if result.status == 'PROGRESS' else None
        )
        
        logger.info("Status check completed", extra={
            "extra_fields": {"task_id": task_id, "status": result.status}
        })
        
        return response
        
    except Exception as e:
        logger.error("Status check failed", extra={
            "extra_fields": {"task_id": task_id, "error": str(e)}
        }, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")