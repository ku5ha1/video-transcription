# Video Call Transcription & Metadata MVP

Modular pipeline to extract audio, transcribe, and tag video call metadata (Emotion/Tone) with speaker diarization.

### Core Stack
- **Transcription:** `faster-whisper` (Local)
- **Diarization:** `AssemblyAI` (API)
- **NLP Metadata:** `BART Zero-Shot` (Local)
- **Video Processing:** `MoviePy`

### Setup
1. `pip install -r requirements.txt`
2. Add `ASSEMBLY_AI_API_KEY` to `.env`

### Run
```bash
# Local
python main.py sample2.mp4

# Docker
docker build -t video-transcription .
docker run --rm -v "$(pwd)":/app --env-file .env video-transcription sample2.mp4