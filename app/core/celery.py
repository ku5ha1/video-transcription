import time
from celery import Celery
from app.services.transcription_service import TranscriptionService
from app.core.logging import get_logger

logger = get_logger("celery")

celery_app = Celery(
    "worker",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0"
)

@celery_app.task
def heavy_lifting_task(name: str):
    time.sleep(30) 
    return f"Hello {name}, your long task is finished!"

@celery_app.task(bind=True)
def process_video_task(self, video_path: str, filename: str):
    """
    Celery task to process video transcription asynchronously
    """
    try:
        logger.info(f"Starting video processing task for {filename}")
        
        # Update task state to PROGRESS
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 100, 'status': 'Starting transcription...'}
        )
        
        # Initialize transcription service
        transcription_service = TranscriptionService()
        
        # Process the video file
        result = transcription_service.process_video_from_path(video_path)
        
        logger.info(f"Video processing completed for {filename}")
        
        # Clean up the shared video file
        try:
            import os
            if os.path.exists(video_path):
                os.unlink(video_path)
                logger.info(f"Cleaned up shared video file: {video_path}")
        except Exception as cleanup_error:
            logger.warning(f"Failed to cleanup video file {video_path}: {cleanup_error}")
        
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
        
        # Clean up the shared video file even on failure
        try:
            import os
            if os.path.exists(video_path):
                os.unlink(video_path)
                logger.info(f"Cleaned up shared video file after error: {video_path}")
        except Exception as cleanup_error:
            logger.warning(f"Failed to cleanup video file after error {video_path}: {cleanup_error}")
        
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'filename': filename}
        )
        raise