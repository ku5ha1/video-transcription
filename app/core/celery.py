import time
from celery import Celery
from app.services.transcription_service import TranscriptionService
from app.services.minio_service import MinIOService
from app.core.logging import get_logger
from app.core.config import settings
import tempfile
import os

logger = get_logger("celery")

celery_app = Celery(
    "worker",
    broker=settings.redis_url,
    backend=settings.redis_url
)

@celery_app.task
def heavy_lifting_task(name: str):
    time.sleep(30) 
    return f"Hello {name}, your long task is finished!"

@celery_app.task(bind=True)
def process_video_task(self, object_name: str, filename: str):
    """
    Celery task to process video transcription asynchronously
    Downloads from MinIO, processes, then cleans up
    """
    temp_video_path = None
    
    try:
        logger.info(f"Starting video processing task for {filename}")
        
        # Update task state to PROGRESS
        self.update_state(
            state='PROGRESS',
            meta={'current': 10, 'total': 100, 'status': 'Downloading video from storage...'}
        )
        
        # Initialize services
        # NOTE: Models (Whisper, BART) are loaded here in Celery worker, not in FastAPI container
        # This keeps FastAPI lightweight and fast, while Celery handles heavy ML processing
        minio_service = MinIOService()
        transcription_service = TranscriptionService()
        
        # Download video from MinIO to temporary file
        temp_video_path = tempfile.mktemp(suffix='.mp4')
        minio_service.download_file(object_name, temp_video_path)
        
        logger.info(f"Downloaded video from MinIO: {object_name}")
        
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={'current': 20, 'total': 100, 'status': 'Starting transcription...'}
        )
        
        # Process the video file
        result = transcription_service.process_video_from_path(temp_video_path)
        
        logger.info(f"Video processing completed for {filename}")
        
        # Clean up MinIO object
        try:
            minio_service.delete_file(object_name)
            logger.info(f"Deleted video from MinIO: {object_name}")
        except Exception as cleanup_error:
            logger.warning(f"Failed to delete MinIO object {object_name}: {cleanup_error}")
        
        # Clean up local temp file
        if temp_video_path and os.path.exists(temp_video_path):
            os.unlink(temp_video_path)
            logger.info(f"Cleaned up temporary file: {temp_video_path}")
        
        return {
            'success': result.success,
            'message': result.message,
            'segments': [segment.dict() for segment in result.segments],
            'total_segments': result.total_segments,
            'processing_time': result.processing_time,
            'filename': filename
        }
        
    except Exception as e:
        logger.error(f"Video processing failed for {filename}: {str(e)}", exc_info=True)
        
        # Clean up on failure
        try:
            minio_service = MinIOService()
            minio_service.delete_file(object_name)
            logger.info(f"Deleted video from MinIO after error: {object_name}")
        except Exception as cleanup_error:
            logger.warning(f"Failed to delete MinIO object after error {object_name}: {cleanup_error}")
        
        if temp_video_path and os.path.exists(temp_video_path):
            os.unlink(temp_video_path)
            logger.info(f"Cleaned up temporary file after error: {temp_video_path}")
        
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'filename': filename}
        )
        raise