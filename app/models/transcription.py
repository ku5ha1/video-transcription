from pydantic import BaseModel
from typing import List, Optional

class TranscriptSegment(BaseModel):
    timestamp: str
    speaker: str
    text: str
    emotion: str
    tone: str
    start_time: float
    end_time: float

class TranscriptionResponse(BaseModel):
    success: bool
    message: str
    segments: List[TranscriptSegment]
    total_segments: int
    processing_time: Optional[float] = None