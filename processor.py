import transcription
import metadata
import utils


def annotate_segment(segment, speaker_id: int) -> str:
    text = segment.text.strip()
    metadata_dict = metadata.get_metadata(text)
    timestamp = utils.format_timestamp(segment.start)
    
    return (
        f"{timestamp} Speaker {speaker_id}: \"{text}\" "
        f"[Emotion: {metadata_dict['Emotion']}, Tone: {metadata_dict['Tone']}]"
    )


def process_video_call(audio_path: str) -> list:
    segments = transcription.transcribe_audio(audio_path)
    transcript = []
    speaker_id = 1
    
    for segment in segments:
        annotated_line = annotate_segment(segment, speaker_id)
        transcript.append(annotated_line)
        speaker_id = 2 if speaker_id == 1 else 1
    
    return transcript

