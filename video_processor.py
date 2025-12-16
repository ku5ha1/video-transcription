import tempfile
from moviepy.editor import VideoFileClip


def extract_audio_from_video(video_path: str) -> str:
    print(f"\nExtracting audio from video: {video_path}")
    video = VideoFileClip(video_path)
    
    temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
    temp_audio_path = temp_audio.name
    temp_audio.close()
    
    video.audio.write_audiofile(temp_audio_path, verbose=False, logger=None)
    video.close()
    
    print(f"Audio extracted to: {temp_audio_path}")
    return temp_audio_path

