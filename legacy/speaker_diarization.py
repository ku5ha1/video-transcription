import os
import assemblyai as aai

aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")


def get_speaker_labels(audio_path: str) -> list:
    print("\nRunning Speaker Diarization with AssemblyAI...")
    
    if not aai.settings.api_key:
        print("WARNING: ASSEMBLYAI_API_KEY not found. Falling back to alternating speakers.")
        return None
    
    transcriber = aai.Transcriber()
    
    try:
        config = aai.TranscriptionConfig(speaker_labels=True)
        transcript = transcriber.transcribe(audio_path, config=config)
        
        if transcript.status == aai.TranscriptStatus.error:
            print(f"ERROR: AssemblyAI transcription failed - {transcript.error}")
            return None
        
        if not transcript.utterances:
            print("WARNING: No utterances found in transcript. Falling back to alternating speakers.")
            return None
        
        speaker_segments = []
        for utterance in transcript.utterances:
            speaker_segments.append({
                "start": utterance.start / 1000.0,
                "end": utterance.end / 1000.0,
                "speaker": utterance.speaker
            })
        
        unique_speakers = len(set(s['speaker'] for s in speaker_segments))
        print(f"Found {unique_speakers} speaker(s)")
        return speaker_segments
        
    except Exception as e:
        print(f"ERROR during AssemblyAI diarization: {e}")
        return None


def align_speakers(whisper_segments, speaker_labels: list) -> dict:
    if not speaker_labels:
        return {}
    
    alignment_map = {}
    
    for segment in whisper_segments:
        segment_start = segment.start
        segment_end = segment.end
        
        best_match = None
        best_overlap = 0
        
        for speaker_seg in speaker_labels:
            speaker_start = speaker_seg["start"]
            speaker_end = speaker_seg["end"]
            
            overlap_start = max(segment_start, speaker_start)
            overlap_end = min(segment_end, speaker_end)
            overlap = max(0, overlap_end - overlap_start)
            
            if overlap > best_overlap:
                best_overlap = overlap
                best_match = speaker_seg["speaker"]
        
        if best_match is not None:
            alignment_map[segment_start] = best_match
    
    return alignment_map

