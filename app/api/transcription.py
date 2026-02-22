from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.transcription import TranscriptionResponse
from app.models.task import TaskResponse, TaskStatusResponse
from app.models.database import User, Video, VideoStatus, TranscriptSegment
from app.schemas.video import VideoResponse, VideoDetailResponse, VideoListResponse, TranscriptSegmentResponse
from app.services.minio_service import MinIOService
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import FileValidationError, create_http_exception
from app.core.config import settings
from app.core.logging import get_logger
from app.core.celery import celery_app, process_video_task
from celery.result import AsyncResult
from typing import List
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
async def transcribe_video(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a video file and start asynchronous transcription processing
    
    Requires authentication. Video will be associated with the authenticated user.
    """
    logger.info("Transcription request received", extra={
        "extra_fields": {
            "filename": file.filename,
            "content_type": file.content_type,
            "user_id": str(current_user.id)
        }
    })
    
    try:
        # Validate file
        validate_file(file)
        logger.info("File validation passed", extra={"extra_fields": {"filename": file.filename}})
        
        # Read file content
        content = await file.read()
        
        # Generate unique object name with user prefix for organization
        file_ext = "." + file.filename.split(".")[-1].lower()
        object_name = f"users/{current_user.id}/videos/{uuid.uuid4()}{file_ext}"
        
        # Upload to MinIO
        minio_service.upload_file(content, object_name, file.content_type or "video/mp4")
        
        logger.info("File uploaded to MinIO", extra={
            "extra_fields": {"filename": file.filename, "object_name": object_name}
        })
        
        # Create video record in database
        video = Video(
            user_id=current_user.id,
            filename=file.filename,
            minio_object_key=object_name,
            status=VideoStatus.PENDING
        )
        db.add(video)
        await db.commit()
        await db.refresh(video)
        
        logger.info("Video record created in database", extra={
            "extra_fields": {"video_id": str(video.id), "user_id": str(current_user.id)}
        })
        
        # Submit task to Celery with user_id and video_id
        task = process_video_task.delay(
            object_name,
            file.filename,
            str(current_user.id),
            str(video.id)
        )
        
        logger.info("Task submitted to Celery", extra={
            "extra_fields": {
                "filename": file.filename,
                "task_id": task.id,
                "video_id": str(video.id),
                "user_id": str(current_user.id)
            }
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


@router.get("/videos", response_model=VideoListResponse)
async def list_videos(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all videos for the authenticated user with pagination
    """
    logger.info(f"Video list requested by user: {current_user.email}")
    
    # Calculate offset
    offset = (page - 1) * page_size
    
    # Get total count
    from sqlalchemy import func
    count_result = await db.execute(
        select(func.count(Video.id)).where(Video.user_id == current_user.id)
    )
    total = count_result.scalar()
    
    # Get paginated videos
    result = await db.execute(
        select(Video)
        .where(Video.user_id == current_user.id)
        .order_by(Video.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    videos = result.scalars().all()
    
    return VideoListResponse(
        videos=videos,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/videos/{video_id}", response_model=VideoDetailResponse)
async def get_video_detail(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get video details with transcript segments
    
    Only returns video if it belongs to the authenticated user
    """
    logger.info(f"Video detail requested: {video_id} by user: {current_user.email}")
    
    # Fetch video with segments
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Video)
        .options(selectinload(Video.transcript_segments))
        .where(Video.id == video_id, Video.user_id == current_user.id)
    )
    video = result.scalar_one_or_none()
    
    if not video:
        logger.warning(f"Video not found or access denied: {video_id}")
        raise HTTPException(
            status_code=404,
            detail="Video not found"
        )
    
    # Manually convert to VideoDetailResponse
    segments = [
        TranscriptSegmentResponse(
            id=s.id,
            video_id=s.video_id,
            start_time=s.start_time,
            end_time=s.end_time,
            speaker_label=s.speaker_label,
            text=s.text,
            audio_emotion=s.audio_emotion,
            text_tone=s.text_tone
        )
        for s in video.transcript_segments
    ]
    
    return VideoDetailResponse(
        id=video.id,
        user_id=video.user_id,
        filename=video.filename,
        status=video.status,
        duration=video.duration,
        created_at=video.created_at,
        segments=segments
    )


@router.delete("/videos/{video_id}")
async def delete_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a video and all its transcript segments
    
    Only allows deletion if video belongs to the authenticated user
    """
    logger.info(f"Video deletion requested: {video_id} by user: {current_user.email}")
    
    # Fetch video
    result = await db.execute(
        select(Video).where(Video.id == video_id, Video.user_id == current_user.id)
    )
    video = result.scalar_one_or_none()
    
    if not video:
        logger.warning(f"Video not found or access denied: {video_id}")
        raise HTTPException(
            status_code=404,
            detail="Video not found"
        )
    
    # Delete from MinIO
    try:
        minio_service.delete_file(video.minio_object_key)
        logger.info(f"Deleted video from MinIO: {video.minio_object_key}")
    except Exception as e:
        logger.warning(f"Failed to delete from MinIO: {e}")
    
    # Delete from database (cascades to segments)
    await db.delete(video)
    await db.commit()
    
    logger.info(f"Video deleted successfully: {video_id}")
    return {"message": "Video deleted successfully", "video_id": video_id}


@router.get("/videos/{video_id}/stream")
async def stream_video(
    video_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Stream video file from MinIO
    
    Returns a presigned URL that redirects to the MinIO object
    """
    from fastapi.responses import RedirectResponse
    
    # Fetch video
    result = await db.execute(
        select(Video).where(Video.id == video_id, Video.user_id == current_user.id)
    )
    video = result.scalar_one_or_none()
    
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Generate presigned URL (valid for 1 hour)
    try:
        presigned_url = minio_service.get_file_url(video.minio_object_key, expires_in_seconds=3600)
        return RedirectResponse(url=presigned_url)
    except Exception as e:
        logger.error(f"Failed to generate presigned URL: {e}")
        raise HTTPException(status_code=500, detail="Failed to stream video")
