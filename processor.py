import transcription
import metadata
import utils
import speaker_diarization

def annotate_segment(segment, speaker_id: str) -> str:
    text = segment.text.strip()
    metadata_dict = metadata.get_metadata(text)
    timestamp = utils.format_timestamp(segment.start)
    
    return (
        f"{timestamp} Speaker {speaker_id}: \"{text}\" "
        f"[Emotion: {metadata_dict['Emotion']}, Tone: {metadata_dict['Tone']}]"
    )

def process_video_call(audio_path: str) -> list:
    segments = list(transcription.transcribe_audio(audio_path))
    speaker_labels = speaker_diarization.get_speaker_labels(audio_path)
    
    if speaker_labels:
        alignment_map = speaker_diarization.align_speakers(segments, speaker_labels)
    else:
        alignment_map = {}
    
    transcript = []
    fallback_speaker = 1
    
    for segment in segments:
        speaker_id = alignment_map.get(segment.start)
        
        if speaker_id is None:
            speaker_id = f"Speaker {fallback_speaker}"
            fallback_speaker = 2 if fallback_speaker == 1 else 1
        else:
            speaker_id = f"Speaker {speaker_id}"
        
        annotated_line = annotate_segment(segment, speaker_id)
        transcript.append(annotated_line)
    
    return transcript

