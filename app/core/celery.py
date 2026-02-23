import time
import asyncio
import tempfile
import os
from celery import Celery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.services.transcription_service import TranscriptionService
from app.services.minio_service import MinIOService
from app.services.vector_store import VectorStoreService
from app.models.database import Video, TranscriptSegment, VideoStatus
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger("celery")

celery_app = Celery("worker", broker=settings.redis_url, backend=settings.redis_url)


@celery_app.task
def heavy_lifting_task(name: str):
    time.sleep(30)
    return f"Hello {name}, your long task is finished!"


@celery_app.task(bind=True)
def process_video_task(
    self, object_name: str, filename: str, user_id: str, video_id: str
):
    """
    Celery task to process video transcription with database persistence
    Downloads from MinIO, processes, saves segments to database, then cleans up

    Uses task-local async engine to avoid event loop conflicts
    """

    # Create task-local async engine and session factory
    # This ensures the engine is bound to THIS task's event loop
    task_engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

    TaskSessionLocal = async_sessionmaker(
        task_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async def update_video_status(status: VideoStatus, duration: float = None):
        """Helper to update video status in database"""
        async with TaskSessionLocal() as db:
            try:
                result = await db.execute(select(Video).where(Video.id == video_id))
                video = result.scalar_one_or_none()
                if video:
                    video.status = status
                    if duration:
                        video.duration = duration
                    await db.commit()
                    logger.info(f"Video status updated to {status}: {video_id}")
            except Exception as e:
                logger.error(f"Failed to update video status: {e}", exc_info=True)
                await db.rollback()

    async def save_segments(segments_data: list):
        """Helper to save transcript segments to database"""
        async with TaskSessionLocal() as db:
            try:
                for seg_data in segments_data:
                    segment = TranscriptSegment(
                        video_id=video_id,
                        user_id=user_id,
                        start_time=seg_data["start_time"],
                        end_time=seg_data["end_time"],
                        speaker_label=seg_data["speaker"],
                        text=seg_data["text"],
                        audio_emotion=seg_data.get("emotion"),
                        text_tone=seg_data.get("tone"),
                    )
                    db.add(segment)
                await db.commit()
                logger.info(
                    f"Saved {len(segments_data)} segments to database for video: {video_id}"
                )

                # Upsert segments to Qdrant vector store
                try:
                    # Re-fetch segments with IDs
                    result = await db.execute(
                        select(TranscriptSegment)
                        .where(TranscriptSegment.video_id == video_id)
                        .order_by(TranscriptSegment.start_time)
                    )
                    segments = result.scalars().all()

                    vector_service = VectorStoreService()
                    vector_service.upsert_segments(segments)
                    logger.info(
                        f"Upserted {len(segments)} segments to Qdrant for video: {video_id}"
                    )
                except Exception as vector_error:
                    logger.warning(f"Failed to upsert to Qdrant: {vector_error}")

            except Exception as e:
                logger.error(f"Failed to save segments: {e}", exc_info=True)
                await db.rollback()
                raise

    async def run_task():
        """Main async task logic"""
        temp_video_path = None

        try:
            logger.info(
                f"Starting video processing task for {filename} (user: {user_id}, video: {video_id})"
            )

            # Update status to PROCESSING
            await update_video_status(VideoStatus.PROCESSING)

            self.update_state(
                state="PROGRESS",
                meta={
                    "current": 10,
                    "total": 100,
                    "status": "Downloading video from storage...",
                },
            )

            # Initialize services
            minio_service = MinIOService()
            transcription_service = TranscriptionService()

            # Download video from MinIO to temporary file
            temp_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            temp_video_path = temp_file.name
            temp_file.close()
            minio_service.download_file(object_name, temp_video_path)

            logger.info(f"Downloaded video from MinIO: {object_name}")

            self.update_state(
                state="PROGRESS",
                meta={
                    "current": 20,
                    "total": 100,
                    "status": "Starting transcription...",
                },
            )

            # Process the video file
            result = transcription_service.process_video_from_path(temp_video_path)

            if result.success:
                # Prepare segments data for database
                segments_data = []
                for segment in result.segments:
                    segments_data.append(
                        {
                            "start_time": segment.start_time,
                            "end_time": segment.end_time,
                            "speaker": segment.speaker,
                            "text": segment.text,
                            "emotion": segment.emotion,
                            "tone": segment.tone,
                        }
                    )

                # Save segments to database
                await save_segments(segments_data)

                # Update video status to COMPLETED
                await update_video_status(VideoStatus.COMPLETED, result.processing_time)

                logger.info(f"Video processing completed for {filename}")
            else:
                # Update status to FAILED
                await update_video_status(VideoStatus.FAILED)
                logger.error(f"Video processing failed: {result.message}")

            # Note: Keep video in MinIO for playback
            # Video will only be deleted when user explicitly deletes it via the API
            logger.info(
                f"Video processing completed, keeping video in MinIO: {object_name}"
            )

            # Clean up local temp file
            if temp_video_path and os.path.exists(temp_video_path):
                os.unlink(temp_video_path)
                logger.info(f"Cleaned up temporary file: {temp_video_path}")

            return {
                "success": result.success,
                "message": result.message,
                "video_id": video_id,
                "total_segments": result.total_segments,
                "processing_time": result.processing_time,
                "filename": filename,
            }

        except Exception as e:
            logger.error(
                f"Video processing failed for {filename}: {str(e)}", exc_info=True
            )

            # Update status to FAILED
            try:
                await update_video_status(VideoStatus.FAILED)
            except Exception:
                pass

            # Note: Keep video in MinIO even on failure for debugging
            # Video will be deleted when user explicitly deletes it via the API
            logger.info(f"Keeping video in MinIO after error: {object_name}")

            if temp_video_path and os.path.exists(temp_video_path):
                os.unlink(temp_video_path)
                logger.info(f"Cleaned up temporary file after error: {temp_video_path}")

            self.update_state(
                state="FAILURE", meta={"error": str(e), "filename": filename}
            )
            raise
        finally:
            # Always cleanup the engine
            await task_engine.dispose()

    # Run the async task with asyncio.run() which properly manages the event loop
    # This creates a new event loop, runs the task, and cleanly closes the loop
    return asyncio.run(run_task())
