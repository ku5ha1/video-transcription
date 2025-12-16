from faster_whisper import WhisperModel
import config


print(f"Loading Transcription Model: faster-whisper ({config.MODEL_SIZE})")
whisper_model = WhisperModel(config.MODEL_SIZE, device=config.DEVICE, compute_type="int8")


def transcribe_audio(audio_path: str):
    print("\nStarting Transcription...")
    segments, _ = whisper_model.transcribe(audio_path, beam_size=5)
    return segments

