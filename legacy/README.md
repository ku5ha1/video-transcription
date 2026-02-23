# Video Transcription System

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
 ```
 
 ## Sample Input
 - **Video:** `sample2.mp4` – short, two-speaker conversation-style clip (simulating a video call).
 - **Invocation:** `python main.py sample2.mp4`
 
 ## Sample Output
 - **File:** `output/final_annotated_transcript.txt`
 - **Example lines:**
   ```text
   [00:00:05] Speaker A: "My daily routine is nothing special." [Emotion: Calmness, Tone: Neutral]
   [00:00:11] Speaker B: "I usually wake up early around 7 a.m." [Emotion: Calmness, Tone: Inquisitive]
   ```
 - Each line includes:
   - timestamp
   - inferred speaker label
   - transcribed text
   - Emotion and Tone tags

```

### Module Overview
- main.py: CLI & Orchestration.
- video_processor.py: Video-to-audio extraction.
- transcription.py: ASR implementation.
- speaker_diarization.py: Speaker identification logic.
- metadata.py: Emotion and Tone classification.
- processor.py: Data merging and formatting.
