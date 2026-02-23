import transcription
import metadata
import utils
import speaker_diarization


def annotate_segment(segment, speaker_label: str) -> str:
    text = segment.text.strip()
    metadata_dict = metadata.get_metadata(text)
    timestamp = utils.format_timestamp(segment.start)
    
    return (
        f"{timestamp} {speaker_label}: \"{text}\" "
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
    speaker_index_map = {}
    next_speaker_index = 1
    
    for segment in segments:
        raw_speaker_id = alignment_map.get(segment.start)
        
        if raw_speaker_id is None:
            speaker_label = f"Speaker {fallback_speaker}"
            fallback_speaker = 2 if fallback_speaker == 1 else 1
        else:
            if raw_speaker_id not in speaker_index_map:
                speaker_index_map[raw_speaker_id] = next_speaker_index
                next_speaker_index += 1
            speaker_label = f"Speaker {speaker_index_map[raw_speaker_id]}"
        
        annotated_line = annotate_segment(segment, speaker_label)
        transcript.append(annotated_line)
    
    return transcript

