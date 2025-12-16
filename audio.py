import os
import time
import tempfile
from faster_whisper import WhisperModel
from transformers import pipeline
from moviepy.editor import VideoFileClip

VIDEO_FILE = "sample.mp4"
AUDIO_FILE = "test.mp3"
DEVICE = "cpu"
MODEL_SIZE = "tiny"

CANDIDATE_EMOTIONS = ["joy", "anger", "sadness", "excitement", "calmness", "interest", "confusion"]
CANDIDATE_TONES = ["enthusiastic", "confident", "inquisitive", "hesitant", "professional", "sarcastic", "neutral"]

print(f"Loading Transcription Model: faster-whisper ({MODEL_SIZE})")
whisper_model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type="int8")

print("Loading Metadata Classifier: Zero-Shot BART")
classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli", device=DEVICE)


def format_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"[{hours:02d}:{minutes:02d}:{secs:02d}]"


def detect_reaction(text: str) -> str:
    lower_text = text.lower()
    positive_phrases = ["great job", "fantastic", "excellent", "i agree"]
    negative_phrases = ["i don't think so", "not sure", "problematic"]
    
    if any(phrase in lower_text for phrase in positive_phrases):
        return "Positive Acknowledgment"
    elif any(phrase in lower_text for phrase in negative_phrases):
        return "Concern/Disagreement"
    return "None"


def get_metadata(text: str) -> dict:
    emotion_result = classifier(text, candidate_labels=CANDIDATE_EMOTIONS, multi_label=False)
    tone_result = classifier(text, candidate_labels=CANDIDATE_TONES, multi_label=False)
    
    return {
        "Emotion": emotion_result['labels'][0].capitalize(),
        "Tone": tone_result['labels'][0].capitalize(),
        "Reaction": detect_reaction(text)
    }


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


def transcribe_audio(audio_path: str):
    print("\nStarting Transcription...")
    segments, _ = whisper_model.transcribe(audio_path, beam_size=5)
    return segments


def annotate_segment(segment, speaker_id: int) -> str:
    text = segment.text.strip()
    metadata = get_metadata(text)
    timestamp = format_timestamp(segment.start)
    
    return (
        f"{timestamp} Speaker {speaker_id}: \"{text}\" "
        f"[Emotion: {metadata['Emotion']}, Tone: {metadata['Tone']}]"
    )


def process_video_call(audio_path: str) -> list:
    segments = transcribe_audio(audio_path)
    transcript = []
    speaker_id = 1
    
    for segment in segments:
        annotated_line = annotate_segment(segment, speaker_id)
        transcript.append(annotated_line)
        speaker_id = 2 if speaker_id == 1 else 1
    
    return transcript


def get_audio_source():
    if os.path.exists(VIDEO_FILE):
        try:
            audio_path = extract_audio_from_video(VIDEO_FILE)
            return audio_path, True
        except Exception as e:
            print(f"\nERROR extracting audio from video: {e}")
            return None, False
    elif os.path.exists(AUDIO_FILE):
        print(f"Using existing audio file: {AUDIO_FILE}")
        return AUDIO_FILE, False
    else:
        print(f"ERROR: Neither video file '{VIDEO_FILE}' nor audio file '{AUDIO_FILE}' found.")
        return None, False


def save_transcript(transcript: list, output_file: str):
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(transcript))
    
    print("\n--- FINAL DELIVERABLE OUTPUT ---")
    print("\n".join(transcript))
    print(f"\nSUCCESS: Transcript saved to {output_file}")


if __name__ == '__main__':
    audio_path, temp_created = get_audio_source()
    
    if not audio_path:
        exit(1)
    
    try:
        transcript = process_video_call(audio_path)
        save_transcript(transcript, "final_annotated_transcript.txt")
        
        if temp_created and os.path.exists(audio_path):
            os.unlink(audio_path)
            print(f"Cleaned up temporary audio file: {audio_path}")
            
    except Exception as e:
        print(f"\nCRITICAL ERROR during execution: {e}")
        if temp_created and audio_path and os.path.exists(audio_path):
            os.unlink(audio_path)
