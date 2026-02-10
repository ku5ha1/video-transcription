import os
import torch
import torchaudio
if not hasattr(torchaudio, 'list_audio_backends'):
    torchaudio.list_audio_backends = lambda: []
if not hasattr(torchaudio, 'io'):
    # Dummy io module to avoid AttributeError
    import types
    torchaudio.io = types.SimpleNamespace()
import assemblyai as aai
from dotenv import load_dotenv
from pyannote.audio import Pipeline
from app.core.logging import get_logger
from app.core.config import settings

load_dotenv()
logger = get_logger("services.diarization")

class DiarizationService:
    """Service for speaker diarization using pyannote.audio with AssemblyAI fallback"""
    
    def __init__(self):
        self.use_pyannote = True
        self.pyannote_pipeline = None
        
        # Try to initialize pyannote
        try:
            hf_token = os.getenv("HUGGING_FACE_TOKEN")
            if hf_token:
                logger.info("Initializing pyannote.audio 3.1 pipeline")
                # FIX 1: Use 'token' parameter (already correct in your code)
                self.pyannote_pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    token=hf_token
                )
                
                # FIX 2: Explicit CPU optimization
                device = torch.device("cuda" if settings.device == "cuda" and torch.cuda.is_available() else "cpu")
                self.pyannote_pipeline.to(device)
                
                # CPU thread optimization to prevent thrashing
                if device.type == "cpu":
                    torch.set_num_threads(4)  # Limit threads for Celery workers
                    logger.info("pyannote.audio initialized on CPU with 4 threads")
                else:
                    logger.info("pyannote.audio initialized on GPU")
            else:
                logger.warning("HUGGING_FACE_TOKEN not found, will use AssemblyAI fallback")
                self.use_pyannote = False
        except Exception as e:
            logger.error(f"Failed to initialize pyannote.audio: {e}, using AssemblyAI fallback")
            self.use_pyannote = False
        
        # Initialize AssemblyAI as fallback
        aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")
    
    def get_speaker_labels(self, audio_path: str) -> list:
        """Get speaker labels from audio file using pyannote or AssemblyAI fallback"""
        
        # Try pyannote first
        if self.use_pyannote and self.pyannote_pipeline:
            try:
                logger.info("Running speaker diarization with pyannote.audio")
                
                # FIX 3: Faster CPU processing by pre-loading with torchaudio
                waveform, sample_rate = torchaudio.load(audio_path)
                
                # Pyannote 3.1 expects dict with waveform and sample_rate
                diarization = self.pyannote_pipeline({
                    "waveform": waveform,
                    "sample_rate": sample_rate
                })
                
                speaker_segments = []
                for turn, _, speaker in diarization.itertracks(yield_label=True):
                    speaker_segments.append({
                        "start": turn.start,
                        "end": turn.end,
                        "speaker": speaker
                    })
                
                unique_speakers = len(set(s['speaker'] for s in speaker_segments))
                logger.info(f"pyannote.audio found {unique_speakers} speaker(s)")
                return speaker_segments
                
            except Exception as e:
                logger.error(f"pyannote.audio failed: {e}, falling back to AssemblyAI")
        
        # Fallback to AssemblyAI
        logger.info("Running speaker diarization with AssemblyAI")
        
        if not aai.settings.api_key:
            logger.warning("ASSEMBLYAI_API_KEY not found. Falling back to alternating speakers.")
            return None
        
        transcriber = aai.Transcriber()
        
        try:
            config = aai.TranscriptionConfig(speaker_labels=True)
            transcript = transcriber.transcribe(audio_path, config=config)
            
            if transcript.status == aai.TranscriptStatus.error:
                logger.error(f"AssemblyAI transcription failed - {transcript.error}")
                return None
            
            if not transcript.utterances:
                logger.warning("No utterances found in transcript. Falling back to alternating speakers.")
                return None
            
            speaker_segments = []
            for utterance in transcript.utterances:
                speaker_segments.append({
                    "start": utterance.start / 1000.0,
                    "end": utterance.end / 1000.0,
                    "speaker": utterance.speaker
                })
            
            unique_speakers = len(set(s['speaker'] for s in speaker_segments))
            logger.info(f"AssemblyAI found {unique_speakers} speaker(s)")
            return speaker_segments
            
        except Exception as e:
            logger.error(f"AssemblyAI diarization failed: {e}")
            return None
    
    def align_speakers(self, whisper_segments, speaker_labels: list) -> dict:
        """Align whisper segments with speaker labels"""
        if not speaker_labels:
            return {}
        
        alignment_map = {}
        
        for segment in whisper_segments:
            segment_start = segment.start
            segment_end = segment.end
            
            # FIX 4: Default to UNKNOWN_SPEAKER to handle silence gaps
            best_match = "UNKNOWN_SPEAKER"
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
            
            # Always assign a speaker (even if UNKNOWN_SPEAKER)
            alignment_map[segment_start] = best_match
        
        return alignment_map