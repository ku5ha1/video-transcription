from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import List, Optional
from app.models.database import VideoStatus


class VideoResponse(BaseModel):
    """Schema for video information response"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    filename: str
    status: VideoStatus
    duration: Optional[float]
    created_at: datetime


class TranscriptSegmentResponse(BaseModel):
    """Schema for transcript segment response"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: UUID
    start_time: float
    end_time: float
    speaker_label: str
    text: str
    audio_emotion: Optional[str]
    text_tone: Optional[str]


class VideoDetailResponse(VideoResponse):
    """Schema for video with transcript segments"""

    model_config = ConfigDict(from_attributes=True)

    segments: List[TranscriptSegmentResponse] = []

    @classmethod
    def model_validate(cls, obj):
        """Custom validation to map transcript_segments to segments"""
        if hasattr(obj, "transcript_segments"):
            # Create a dict from the SQLAlchemy model
            data = {
                "id": obj.id,
                "user_id": obj.user_id,
                "filename": obj.filename,
                "status": obj.status,
                "duration": obj.duration,
                "created_at": obj.created_at,
                "segments": [
                    TranscriptSegmentResponse(
                        id=s.id,
                        video_id=s.video_id,
                        start_time=s.start_time,
                        end_time=s.end_time,
                        speaker_label=s.speaker_label,
                        text=s.text,
                        audio_emotion=s.audio_emotion,
                        text_tone=s.text_tone,
                    )
                    for s in obj.transcript_segments
                ],
            }
            return super().model_validate(data)
        return super().model_validate(obj)


class VideoListResponse(BaseModel):
    """Schema for paginated video list"""

    videos: List[VideoResponse]
    total: int
    page: int
    page_size: int
