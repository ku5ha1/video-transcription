import os
import tempfile
import subprocess
import assemblyai as aai
import sherpa_onnx
import soundfile as sf
import numpy as np
from dotenv import load_dotenv
from app.core.logging import get_logger
from app.core.config import settings

load_dotenv()
logger = get_logger("services.diarization")

class DiarizationService:
    """Service for speaker diarization using Sherpa-ONNX with AssemblyAI fallback"""
    
    def __init__(self):
        self.use_sherpa = True
        self.diarizer = None
        
        # Setup Sherpa-ONNX paths
        base_dir = os.getenv("SHERPA_MODEL_DIR", os.path.join(os.getcwd(), "sherpa-onnx"))
        seg_model = os.path.join(base_dir, "sherpa-onnx-pyannote-segmentation-3-0/model.onnx")
        emb_model = os.path.join(base_dir, "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx")
        
        # Initialize Sherpa-ONNX
        try:
            logger.info("Initializing Sherpa-ONNX speaker diarization")
            config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
                segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
                    pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=seg_model)
                ),
                embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=emb_model),
                clustering=sherpa_onnx.FastClusteringConfig(num_clusters=0, threshold=0.8)
            )
            self.diarizer = sherpa_onnx.OfflineSpeakerDiarization(config)
            logger.info("Sherpa-ONNX diarization initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Sherpa-ONNX: {e}, using AssemblyAI fallback")
            self.use_sherpa = False
        
        # Initialize AssemblyAI as fallback
        aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")
    
    def _preprocess_audio(self, audio_path: str) -> str:
        """Convert audio to 16kHz mono WAV format required by Sherpa-ONNX"""
        try:
            temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix='_16k.wav')
            output_path = temp_audio.name
            temp_audio.close()
            
            # Use ffmpeg to convert to 16kHz mono
            cmd = [
                'ffmpeg', '-i', audio_path,
                '-ar', '16000',
                '-ac', '1',
                '-y',
                output_path
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"Audio preprocessed to 16kHz mono: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Audio preprocessing failed: {e}")
            raise
    
    def get_speaker_labels(self, audio_path: str) -> list:
        """Get speaker labels from audio file using Sherpa-ONNX or AssemblyAI fallback"""
        
        # Try Sherpa-ONNX first
        if self.use_sherpa and self.diarizer:
            try:
                logger.info("Running speaker diarization with Sherpa-ONNX")
                
                # Preprocess audio to 16kHz mono
                processed_audio = self._preprocess_audio(audio_path)
                
                try:
                    # Load audio
                    samples, sample_rate = sf.read(processed_audio, dtype="float32")
                    
                    # Convert to mono if stereo
                    if len(samples.shape) > 1:
                        samples = np.mean(samples, axis=1)
                    
                    # Validate sample rate
                    if sample_rate != 16000:
                        logger.error(f"Invalid sample rate: {sample_rate}, expected 16000")
                        raise ValueError(f"Sample rate must be 16000Hz, got {sample_rate}Hz")
                    
                    # Run diarization
                    result = self.diarizer.process(samples)
                    segments = result.sort_by_start_time()
                    
                    speaker_segments = []
                    for seg in segments:
                        speaker_segments.append({
                            "start": seg.start,
                            "end": seg.end,
                            "speaker": f"SPEAKER_{seg.speaker}"
                        })
                    
                    unique_speakers = len(set(s['speaker'] for s in speaker_segments))
                    logger.info(f"Sherpa-ONNX found {unique_speakers} speaker(s)")
                    return speaker_segments
                    
                finally:
                    # Cleanup preprocessed audio
                    if os.path.exists(processed_audio):
                        os.unlink(processed_audio)
                
            except Exception as e:
                logger.error(f"Sherpa-ONNX failed: {e}, falling back to AssemblyAI")
        
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
        """Align whisper segments with speaker labels using overlap-based matching"""
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
                
                # Calculate overlap duration
                overlap_start = max(segment_start, speaker_start)
                overlap_end = min(segment_end, speaker_end)
                overlap = max(0, overlap_end - overlap_start)
                
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_match = speaker_seg["speaker"]
            
            # Assign speaker if overlap found
            if best_match:
                alignment_map[segment_start] = best_match
        
        logger.info(f"Aligned {len(alignment_map)} segments with speakers")
        return alignment_map
