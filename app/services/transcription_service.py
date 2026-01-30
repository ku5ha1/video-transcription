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

class TranscriptionService:
    def __init__(self):
        # Initialize all services
        self.video_service = VideoService()
        self.whisper_service = WhisperService()
        self.diarization_service = DiarizationService()
        self.metadata_service = MetadataService()
    
    def _annotate_segment(self, segment, speaker_label: str) -> TranscriptSegment:
        """Annotate a single segment with metadata"""
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
    
    async def process_video(self, file: UploadFile) -> TranscriptionResponse:
        """
        Process uploaded video file and return transcription with metadata
        """
        start_time = time.time()
        temp_video_path = None
        temp_audio_path = None
        
        try:
            # Save uploaded video temporarily
            temp_video_path = await self.video_service.save_uploaded_video(file)
            
            # Extract audio from video
            temp_audio_path = await self.video_service.extract_audio_from_video(temp_video_path)
            
            # Transcribe audio
            whisper_segments = list(self.whisper_service.transcribe_audio(temp_audio_path))
            
            # Get speaker labels
            speaker_labels = self.diarization_service.get_speaker_labels(temp_audio_path)
            
            # Align speakers with segments
            if speaker_labels:
                alignment_map = self.diarization_service.align_speakers(whisper_segments, speaker_labels)
            else:
                alignment_map = {}
            
            # Process segments with speaker assignment and metadata
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
            
            return TranscriptionResponse(
                success=True,
                message="Transcription completed successfully",
                segments=segments,
                total_segments=len(segments),
                processing_time=processing_time
            )
            
        except Exception as e:
            return TranscriptionResponse(
                success=False,
                message=f"Processing failed: {str(e)}",
                segments=[],
                total_segments=0,
                processing_time=time.time() - start_time
            )
            
        finally:
            # Clean up temporary files
            if temp_video_path:
                cleanup_file(temp_video_path)
            if temp_audio_path:
                cleanup_file(temp_audio_path)