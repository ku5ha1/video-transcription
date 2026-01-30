import tempfile
import os
from moviepy.editor import VideoFileClip
from fastapi import UploadFile

class VideoService:
    """Service for video processing operations"""
    
    async def extract_audio_from_video(self, video_path: str) -> str:
        """Extract audio from video file and return temporary audio file path"""
        print(f"Extracting audio from video: {video_path}")
        
        video = VideoFileClip(video_path)
        
        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        temp_audio_path = temp_audio.name
        temp_audio.close()
        
        video.audio.write_audiofile(temp_audio_path, verbose=False, logger=None)
        video.close()
        
        print(f"Audio extracted to: {temp_audio_path}")
        return temp_audio_path
    
    async def save_uploaded_video(self, file: UploadFile) -> str:
        """Save uploaded video file temporarily and return path"""
        temp_video = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
        content = await file.read()
        temp_video.write(content)
        temp_video.close()
        return temp_video.name