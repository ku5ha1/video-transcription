import os
import time
from fastapi import UploadFile
from app.models.transcription import TranscriptionResponse, TranscriptSegment
from app.services.video_service import VideoService
from app.services.whisper_service import WhisperService
from app.services.diarization_service import DiarizationService
from app.services.metadata_service import MetadataService
from app.utils.time_utils import format_timestamp
from app.utils.file_utils import cleanup_file
from app.core.exceptions import (
    VideoProcessingError, AudioExtractionError, 
    TranscriptionModelError, SpeakerDiarizationError, 
    MetadataExtractionError
)
from app.core.logging import get_logger

logger = get_logger("services.transcription")

class TranscriptionService:
    def __init__(self):
        logger.info("Initializing TranscriptionService")
        try:
            # Initialize all services
            self.video_service = VideoService()
            self.whisper_service = WhisperService()
            self.diarization_service = DiarizationService()
            self.metadata_service = MetadataService()
            logger.info("All services initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize services", exc_info=True)
            raise
    
    def _annotate_segment(self, segment, speaker_label: str) -> TranscriptSegment:
        """Annotate a single segment with metadata"""
        try:
            text = segment.text.strip()
            metadata_dict = self.metadata_service.get_metadata(text)
            timestamp = format_timestamp(segment.start)
            
            return TranscriptSegment(
                timestamp=timestamp,
                speaker=speaker_label,
                text=text,
                emotion=metadata_dict['Emotion'],
                tone=metadata_dict['Tone']
            )
        except Exception as e:
            logger.error("Failed to annotate segment", extra={
                "extra_fields": {"text": text[:50], "speaker": speaker_label}
            }, exc_info=True)
            raise MetadataExtractionError(f"Failed to extract metadata: {str(e)}")
    
    async def process_video(self, file: UploadFile) -> TranscriptionResponse:
        """
        Process uploaded video file and return transcription with metadata
        """
        start_time = time.time()
        temp_video_path = None
        temp_audio_path = None
        
        logger.info("Starting video processing", extra={
            "extra_fields": {"filename": file.filename}
        })
        
        try:
            # Save uploaded video temporarily
            logger.info("Saving uploaded video")
            temp_video_path = await self.video_service.save_uploaded_video(file)
            
            # Extract audio from video
            logger.info("Extracting audio from video")
            temp_audio_path = await self.video_service.extract_audio_from_video(temp_video_path)
            
            # Transcribe audio
            logger.info("Starting transcription")
            whisper_segments = list(self.whisper_service.transcribe_audio(temp_audio_path))
            logger.info("Transcription completed", extra={
                "extra_fields": {"segments_count": len(whisper_segments)}
            })
            
            # Get speaker labels
            logger.info("Starting speaker diarization")
            speaker_labels = self.diarization_service.get_speaker_labels(temp_audio_path)
            
            # Align speakers with segments
            if speaker_labels:
                alignment_map = self.diarization_service.align_speakers(whisper_segments, speaker_labels)
                logger.info("Speaker alignment completed", extra={
                    "extra_fields": {"aligned_segments": len(alignment_map)}
                })
            else:
                alignment_map = {}
                logger.warning("No speaker labels found, using fallback speaker assignment")
            
            # Process segments with speaker assignment and metadata
            logger.info("Processing segments with metadata")
            segments = []
            fallback_speaker = 1
            speaker_index_map = {}
            next_speaker_index = 1
            
            for segment in whisper_segments:
                raw_speaker_id = alignment_map.get(segment.start)
                
                if raw_speaker_id is None:
                    speaker_label = f"Speaker {fallback_speaker}"
                    fallback_speaker = 2 if fallback_speaker == 1 else 1
                else:
                    if raw_speaker_id not in speaker_index_map:
                        speaker_index_map[raw_speaker_id] = next_speaker_index
                        next_speaker_index += 1
                    speaker_label = f"Speaker {speaker_index_map[raw_speaker_id]}"
                
                annotated_segment = self._annotate_segment(segment, speaker_label)
                segments.append(annotated_segment)
            
            processing_time = time.time() - start_time
            
            logger.info("Video processing completed successfully", extra={
                "extra_fields": {
                    "filename": file.filename,
                    "total_segments": len(segments),
                    "processing_time": processing_time
                }
            })
            
            return TranscriptionResponse(
                success=True,
                message="Transcription completed successfully",
                segments=segments,
                total_segments=len(segments),
                processing_time=processing_time
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error("Video processing failed", extra={
                "extra_fields": {
                    "filename": file.filename,
                    "processing_time": processing_time,
                    "error": str(e)
                }
            }, exc_info=True)
            
            return TranscriptionResponse(
                success=False,
                message=f"Processing failed: {str(e)}",
                segments=[],
                total_segments=0,
                processing_time=processing_time
            )
            
        finally:
            # Clean up temporary files
            if temp_video_path:
                cleanup_file(temp_video_path)
                logger.info("Cleaned up temporary video file")
            if temp_audio_path:
                cleanup_file(temp_audio_path)
                logger.info("Cleaned up temporary audio file")

    def process_video_from_path(self, video_path: str) -> TranscriptionResponse:
        """
        Process video file from file path (for Celery tasks)
        """
        start_time = time.time()
        temp_audio_path = None
        
        logger.info("Starting video processing from path", extra={
            "extra_fields": {"video_path": video_path}
        })
        
        try:
            # Extract audio from video
            logger.info("Extracting audio from video")
            temp_audio_path = self._extract_audio_from_video_path(video_path)
            
            # Transcribe audio
            logger.info("Starting transcription")
            whisper_segments = list(self.whisper_service.transcribe_audio(temp_audio_path))
            logger.info("Transcription completed", extra={
                "extra_fields": {"segments_count": len(whisper_segments)}
            })
            
            # Get speaker labels
            logger.info("Starting speaker diarization")
            speaker_labels = self.diarization_service.get_speaker_labels(temp_audio_path)
            
            # Align speakers with segments
            if speaker_labels:
                alignment_map = self.diarization_service.align_speakers(whisper_segments, speaker_labels)
                logger.info("Speaker alignment completed", extra={
                    "extra_fields": {"aligned_segments": len(alignment_map)}
                })
            else:
                alignment_map = {}
                logger.warning("No speaker labels found, using fallback speaker assignment")
            
            # Process segments with speaker assignment and metadata
            logger.info("Processing segments with metadata")
            segments = []
            fallback_speaker = 1
            speaker_index_map = {}
            next_speaker_index = 1
            
            for segment in whisper_segments:
                raw_speaker_id = alignment_map.get(segment.start)
                
                if raw_speaker_id is None:
                    speaker_label = f"Speaker {fallback_speaker}"
                    fallback_speaker = 2 if fallback_speaker == 1 else 1
                else:
                    if raw_speaker_id not in speaker_index_map:
                        speaker_index_map[raw_speaker_id] = next_speaker_index
                        next_speaker_index += 1
                    speaker_label = f"Speaker {speaker_index_map[raw_speaker_id]}"
                
                annotated_segment = self._annotate_segment(segment, speaker_label)
                segments.append(annotated_segment)
            
            processing_time = time.time() - start_time
            
            logger.info("Video processing completed successfully", extra={
                "extra_fields": {
                    "video_path": video_path,
                    "total_segments": len(segments),
                    "processing_time": processing_time
                }
            })
            
            return TranscriptionResponse(
                success=True,
                message="Transcription completed successfully",
                segments=segments,
                total_segments=len(segments),
                processing_time=processing_time
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error("Video processing failed", extra={
                "extra_fields": {
                    "video_path": video_path,
                    "processing_time": processing_time,
                    "error": str(e)
                }
            }, exc_info=True)
            
            return TranscriptionResponse(
                success=False,
                message=f"Processing failed: {str(e)}",
                segments=[],
                total_segments=0,
                processing_time=processing_time
            )
            
        finally:
            # Clean up temporary audio file
            if temp_audio_path:
                cleanup_file(temp_audio_path)
                logger.info("Cleaned up temporary audio file")
    
    def _extract_audio_from_video_path(self, video_path: str) -> str:
        """Extract audio from video file path"""
        from moviepy.editor import VideoFileClip
        import tempfile
        
        logger.info(f"Extracting audio from video: {video_path}")
        
        video = VideoFileClip(video_path)
        
        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_audio_path = temp_audio.name
        temp_audio.close()
        
        video.audio.write_audiofile(temp_audio_path, verbose=False, logger=None)
        video.close()
        
        logger.info(f"Audio extracted to: {temp_audio_path}")
        return temp_audio_path