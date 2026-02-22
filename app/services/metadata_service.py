import os
import torch
import torchaudio
import numpy as np
from transformers import (
    AutoModelForAudioClassification,
    AutoFeatureExtractor,
    pipeline
)
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("services.metadata")

class MetadataService:
    """Service for dual-layer emotion and tone detection"""
    
    def __init__(self):
        logger.info("Initializing MetadataService with dual-layer architecture")
        
        # Audio Emotion Model (Wav2Vec2)
        logger.info("Loading Audio Emotion Model: Dpngtm/wav2vec2-emotion-recognition")
        huggingface_token = os.getenv("HUGGING_FACE_TOKEN")
        self.audio_model = AutoModelForAudioClassification.from_pretrained(
            "Dpngtm/wav2vec2-emotion-recognition",
            cache_dir=settings.emotion_model_cache_dir,
            token=huggingface_token if huggingface_token else None
        )
        self.audio_feature_extractor = AutoFeatureExtractor.from_pretrained(
            "Dpngtm/wav2vec2-emotion-recognition",
            cache_dir=settings.emotion_model_cache_dir,
            token=huggingface_token if huggingface_token else None
        )
        self.audio_model.eval()
        logger.info("Audio Emotion Model loaded successfully")
        
        # Text Tone Classifier (DeBERTa)
        logger.info("Loading Text Tone Classifier: cross-encoder/nli-deberta-v3-small")
        self.tone_classifier = pipeline(
            "zero-shot-classification",
            model="cross-encoder/nli-deberta-v3-small",
            device=0 if settings.device == "cuda" and torch.cuda.is_available() else -1,
            model_kwargs={"cache_dir": settings.tone_model_cache_dir}
        )
        logger.info("Text Tone Classifier loaded successfully")
        
        # Tone labels for meeting context
        self.tone_labels = [
            "Informative",
            "Questioning",
            "Directive",
            "Suggestive",
            "Agreement",
            "Disagreement",
            "Concerned",
            "Neutral"
        ]
    
    def _resample_audio(self, audio_array: np.ndarray, orig_sr: int, target_sr: int = 16000) -> np.ndarray:
        """Resample audio to target sample rate"""
        if orig_sr == target_sr:
            return audio_array
        
        # Convert to torch tensor
        audio_tensor = torch.from_numpy(audio_array).float()
        
        # Add channel dimension if needed
        if audio_tensor.dim() == 1:
            audio_tensor = audio_tensor.unsqueeze(0)
        
        # Resample
        resampler = torchaudio.transforms.Resample(orig_sr, target_sr)
        resampled = resampler(audio_tensor)
        
        return resampled.squeeze().numpy()
    
    def _convert_to_mono(self, audio_array: np.ndarray) -> np.ndarray:
        """Convert stereo audio to mono"""
        if audio_array.ndim > 1:
            return np.mean(audio_array, axis=0)
        return audio_array
    
    def detect_audio_emotion(self, audio_chunk: np.ndarray, sample_rate: int) -> str:
        """
        Detect emotion from audio using Wav2Vec2
        
        Args:
            audio_chunk: Audio data as numpy array
            sample_rate: Original sample rate of the audio
            
        Returns:
            Detected emotion label
        """
        try:
            # Preprocess audio
            audio_mono = self._convert_to_mono(audio_chunk)
            audio_16k = self._resample_audio(audio_mono, sample_rate, 16000)
            
            # Extract features
            inputs = self.audio_feature_extractor(
                audio_16k,
                sampling_rate=16000,
                return_tensors="pt",
                padding=True
            )
            
            # Run inference
            with torch.no_grad():
                logits = self.audio_model(**inputs).logits
            
            # Get prediction
            predicted_id = torch.argmax(logits, dim=-1).item()
            emotion = self.audio_model.config.id2label[predicted_id]
            
            logger.debug(f"Detected audio emotion: {emotion}")
            return emotion
            
        except Exception as e:
            logger.error(f"Audio emotion detection failed: {e}")
            return "Neutral"
    
    def detect_text_tone(self, text: str) -> str:
        """
        Detect tone from text using DeBERTa Zero-Shot Classification
        
        Args:
            text: Text segment to analyze
            
        Returns:
            Detected tone label
        """
        try:
            if not text or len(text.strip()) < 3:
                return "Neutral"
            
            result = self.tone_classifier(
                text,
                candidate_labels=self.tone_labels,
                multi_label=False
            )
            
            tone = result['labels'][0]
            confidence = result['scores'][0]
            
            logger.debug(f"Detected text tone: {tone} (confidence: {confidence:.2f})")
            return tone
            
        except Exception as e:
            logger.error(f"Text tone detection failed: {e}")
            return "Neutral"
    
    def get_metadata(self, text: str, audio_chunk: np.ndarray = None, sample_rate: int = None) -> dict:
        """
        Get comprehensive metadata from text and optional audio
        
        Args:
            text: Text segment to analyze
            audio_chunk: Optional audio data for emotion detection
            sample_rate: Sample rate of audio_chunk
            
        Returns:
            Dictionary with Emotion and Tone
        """
        # Detect text tone (always available)
        tone = self.detect_text_tone(text)
        
        # Detect audio emotion if audio is provided
        if audio_chunk is not None and sample_rate is not None:
            emotion = self.detect_audio_emotion(audio_chunk, sample_rate)
        else:
            # Fallback: use tone as emotion if no audio
            emotion = tone
        
        return {
            "Emotion": emotion,
            "Tone": tone
        }
