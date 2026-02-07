from fastapi import APIRouter, UploadFile, File, HTTPException
from app.models.transcription import TranscriptionResponse
from app.models.task import TaskResponse, TaskStatusResponse
from app.services.minio_service import MinIOService
from app.core.exceptions import FileValidationError, create_http_exception
from app.core.config import settings
from app.core.logging import get_logger
from app.core.celery import celery_app, process_video_task
from celery.result import AsyncResult
import uuid

logger = get_logger("api.transcription")
router = APIRouter()
minio_service = MinIOService()

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
        
        # Read file content
        content = await file.read()
        
        # Generate unique object name
        file_ext = "." + file.filename.split(".")[-1].lower()
        object_name = f"{uuid.uuid4()}{file_ext}"
        
        # Upload to MinIO
        minio_service.upload_file(content, object_name, file.content_type or "video/mp4")
        
        logger.info("File uploaded to MinIO", extra={
            "extra_fields": {"filename": file.filename, "object_name": object_name}
        })
        
        # Submit task to Celery with MinIO object name
        task = process_video_task.delay(object_name, file.filename)
        
        logger.info("Task submitted to Celery", extra={
            "extra_fields": {"filename": file.filename, "task_id": task.id, "object_name": object_name}
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