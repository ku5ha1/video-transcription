from transformers import pipeline
from app.core.config import settings

class MetadataService:
    """Service for emotion and tone detection"""
    
    def __init__(self):
        print("Loading Metadata Classifier: Zero-Shot BART")
        self.classifier = pipeline(
            "zero-shot-classification", 
            model="facebook/bart-large-mnli", 
            device=settings.device
        )
    
    def detect_reaction(self, text: str) -> str:
        """Detect reaction type from text"""
        lower_text = text.lower()
        positive_phrases = ["great job", "fantastic", "excellent", "i agree"]
        negative_phrases = ["i don't think so", "not sure", "problematic"]
        
        if any(phrase in lower_text for phrase in positive_phrases):
            return "Positive Acknowledgment"
        elif any(phrase in lower_text for phrase in negative_phrases):
            return "Concern/Disagreement"
        return "None"
    
    def get_metadata(self, text: str) -> dict:
        """Get emotion and tone metadata from text"""
        emotion_result = self.classifier(
            text, 
            candidate_labels=settings.candidate_emotions, 
            multi_label=False
        )
        tone_result = self.classifier(
            text, 
            candidate_labels=settings.candidate_tones, 
            multi_label=False
        )
        
        return {
            "Emotion": emotion_result['labels'][0].capitalize(),
            "Tone": tone_result['labels'][0].capitalize(),
            "Reaction": self.detect_reaction(text)
        }