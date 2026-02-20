# import os
# import torch
# import assemblyai as aai
# from dotenv import load_dotenv
# from speechbrain.inference.speaker import SpeakerDiarization
# from app.core.logging import get_logger
# from app.core.config import settings
# import torchaudio
# try:
#     torchaudio.list_audio_backends()
# except AttributeError:
#     torchaudio.list_audio_backends = lambda: []

# load_dotenv()
# logger = get_logger("services.diarization")

# class DiarizationService:
#     """Service for speaker diarization using SpeechBrain with AssemblyAI fallback"""
    
#     def __init__(self):
#         self.use_speechbrain = True
#         self.diarizer = None
        
#         # Try to initialize SpeechBrain
#         try:
#             logger.info("Initializing SpeechBrain speaker diarization")
#             self.diarizer = SpeakerDiarization.from_hparams(
#                 source="speechbrain/spkdiarization-ecapa-voxceleb",
#                 savedir="pretrained_models/diarization"
#             )
            
#             # CPU optimization
#             device = torch.device("cuda" if settings.device == "cuda" and torch.cuda.is_available() else "cpu")
#             if device.type == "cpu":
#                 torch.set_num_threads(4)
#                 logger.info("SpeechBrain diarization initialized on CPU with 4 threads")
#             else:
#                 logger.info("SpeechBrain diarization initialized on GPU")
#         except Exception as e:
#             logger.error(f"Failed to initialize SpeechBrain: {e}, using AssemblyAI fallback")
#             self.use_speechbrain = False
        
#         # Initialize AssemblyAI as fallback
#         aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")
    
#     def get_speaker_labels(self, audio_path: str) -> list:
#         """Get speaker labels from audio file using SpeechBrain or AssemblyAI fallback"""
        
#         # Try SpeechBrain first
#         if self.use_speechbrain and self.diarizer:
#             try:
#                 logger.info("Running speaker diarization with SpeechBrain")
                
#                 # Run SpeechBrain diarization
#                 diarization = self.diarizer.diarize_file(audio_path)
                
#                 speaker_segments = []
#                 for segment in diarization:
#                     speaker_segments.append({
#                         "start": segment.start,
#                         "end": segment.end,
#                         "speaker": f"SPEAKER_{segment.speaker}"
#                     })
                
#                 unique_speakers = len(set(s['speaker'] for s in speaker_segments))
#                 logger.info(f"SpeechBrain found {unique_speakers} speaker(s)")
#                 return speaker_segments
                
#             except Exception as e:
#                 logger.error(f"SpeechBrain failed: {e}, falling back to AssemblyAI")
        
#         # Fallback to AssemblyAI
#         logger.info("Running speaker diarization with AssemblyAI")
        
#         if not aai.settings.api_key:
#             logger.warning("ASSEMBLYAI_API_KEY not found. Falling back to alternating speakers.")
#             return None
        
#         transcriber = aai.Transcriber()
        
#         try:
#             config = aai.TranscriptionConfig(speaker_labels=True)
#             transcript = transcriber.transcribe(audio_path, config=config)
            
#             if transcript.status == aai.TranscriptStatus.error:
#                 logger.error(f"AssemblyAI transcription failed - {transcript.error}")
#                 return None
            
#             if not transcript.utterances:
#                 logger.warning("No utterances found in transcript. Falling back to alternating speakers.")
#                 return None
            
#             speaker_segments = []
#             for utterance in transcript.utterances:
#                 speaker_segments.append({
#                     "start": utterance.start / 1000.0,
#                     "end": utterance.end / 1000.0,
#                     "speaker": utterance.speaker
#                 })
            
#             unique_speakers = len(set(s['speaker'] for s in speaker_segments))
#             logger.info(f"AssemblyAI found {unique_speakers} speaker(s)")
#             return speaker_segments
            
#         except Exception as e:
#             logger.error(f"AssemblyAI diarization failed: {e}")
#             return None
    
#     def align_speakers(self, whisper_segments, speaker_labels: list) -> dict:
#         """Align whisper segments with speaker labels"""
#         if not speaker_labels:
#             return {}
        
#         alignment_map = {}
        
#         for segment in whisper_segments:
#             segment_start = segment.start
#             segment_end = segment.end
            
#             # FIX 4: Default to UNKNOWN_SPEAKER to handle silence gaps
#             best_match = "UNKNOWN_SPEAKER"
#             best_overlap = 0
            
#             for speaker_seg in speaker_labels:
#                 speaker_start = speaker_seg["start"]
#                 speaker_end = speaker_seg["end"]
                
#                 overlap_start = max(segment_start, speaker_start)
#                 overlap_end = min(segment_end, speaker_end)
#                 overlap = max(0, overlap_end - overlap_start)
                
#                 if overlap > best_overlap:
#                     best_overlap = overlap
#                     best_match = speaker_seg["speaker"]
            
#             # Always assign a speaker (even if UNKNOWN_SPEAKER)
#             alignment_map[segment_start] = best_match
        
#         return alignment_map

import sherpa_onnx
import soundfile as sf
import os
import numpy as np

# 1. Setup Paths
# BASE_DIR = "/home/kushal/mydev/video-transcription/sherpa-onnx"
# Path to script directory so it can find input.wav correctly
# SCRIPT_DIR = "/home/kushal/mydev/video-transcription/app/services"

SEG_MODEL = os.path.join(BASE_DIR, "sherpa-onnx-pyannote-segmentation-3-0/model.onnx")
EMB_MODEL = os.path.join(BASE_DIR, "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx")
audio_file = os.path.join(SCRIPT_DIR, "input_16k.wav") # Use the converted file

config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
    segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
        pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=SEG_MODEL)
    ),
    embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=EMB_MODEL),
    clustering=sherpa_onnx.FastClusteringConfig(num_clusters=0, threshold=0.8)
)

# 2. Initialize
sd = sherpa_onnx.OfflineSpeakerDiarization(config)

# 3. Load and Validate Audio
if not os.path.exists(audio_file):
    print(f"File not found: {audio_file}. Did you run the ffmpeg command?")
else:
    samples, sample_rate = sf.read(audio_file, dtype="float32")
    
    # Convert to Mono if still Stereo (average the channels)
    if len(samples.shape) > 1:
        samples = np.mean(samples, axis=1)

    # Final Sample Rate Check
    if sample_rate != 16000:
        print(f"Error: Sample rate is {sample_rate}, but Sherpa-ONNX needs 16000Hz.")
    else:
        # 4. Process
        result = sd.process(samples)
        segments = result.sort_by_start_time() 

        for s in segments:
            print(f"[{s.start:6.2f}s -> {s.end:6.2f}s] Speaker {s.speaker}")