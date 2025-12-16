import os
import time
from faster_whisper import WhisperModel
from transformers import pipeline

AUDIO_FILE = "test.mp3" 
DEVICE = "cpu"  
MODEL_SIZE = "tiny" 

print(f"Loading Transcription Model: faster-whisper ({MODEL_SIZE})")

whisper_model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type="int8") 

print("Loading Metadata Classifier: Zero-Shot BART")
classifier = pipeline(
    "zero-shot-classification",
    model="facebook/bart-large-mnli",
    device=DEVICE 
)

CANDIDATE_EMOTIONS = ["joy", "anger", "sadness", "excitement", "calmness", "interest", "confusion"]
CANDIDATE_TONES = ["enthusiastic", "confident", "inquisitive", "hesitant", "professional", "sarcastic", "neutral"]

def format_timestamp(seconds: float) -> str:
    """Converts seconds float to [HH:MM:SS] format."""
    return time.strftime('[%M:%S]', time.gmtime(seconds))

def get_metadata(text: str) -> dict:
    """Uses zero-shot classification to determine emotion and tone."""

    emotion_result = classifier(text, candidate_labels=CANDIDATE_EMOTIONS, multi_label=False)
    emotion = emotion_result['labels'][0].capitalize()

    tone_result = classifier(text, candidate_labels=CANDIDATE_TONES, multi_label=False)
    tone = tone_result['labels'][0].capitalize()

    reaction = "None"
    lower_text = text.lower()
    if any(word in lower_text for word in ["great job", "fantastic", "excellent", "i agree"]):
        reaction = "Positive Acknowledgment"
    elif any(word in lower_text for word in ["i don't think so", "not sure", "problematic"]):
        reaction = "Concern/Disagreement"

    return {"Emotion": emotion, "Tone": tone, "Reaction": reaction}


def process_video_call(audio_path: str) -> list:
    """Full pipeline: Transcribe, Annotate, and Format."""

    print("\nStarting Transcription...")
    segments, _ = whisper_model.transcribe(audio_path, beam_size=5)
    
    final_transcript = []

    speaker_id = 1
    
    for i, segment in enumerate(segments):
        text = segment.text.strip()

        metadata = get_metadata(text)

        timestamp_str = format_timestamp(segment.start)

        output_line = (
            f"{timestamp_str} Speaker {speaker_id}: \"{text}\" "
            f"[Emotion: {metadata['Emotion']}, Tone: {metadata['Tone']}]"
        )
        final_transcript.append(output_line)

        speaker_id = 2 if speaker_id == 1 else 1
        
    return final_transcript


if __name__ == '__main__':
    if os.path.exists(AUDIO_FILE):
        try:
            final_output = process_video_call(AUDIO_FILE)

            OUTPUT_FILE = "final_annotated_transcript.txt"
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                f.write("\n".join(final_output))

            print("\n--- FINAL DELIVERABLE OUTPUT ---")
            print("\n".join(final_output))
            print(f"\nSUCCESS: Transcript saved to {OUTPUT_FILE}")
            
        except Exception as e:
            print(f"\nCRITICAL ERROR during execution: {e}")
            
    else:
        print(f"ERROR: Audio file '{AUDIO_FILE}' not found. Please ensure it is available.")