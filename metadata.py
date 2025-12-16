from transformers import pipeline
import config


print("Loading Metadata Classifier: Zero-Shot BART")
classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli", device=config.DEVICE)


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
    emotion_result = classifier(text, candidate_labels=config.CANDIDATE_EMOTIONS, multi_label=False)
    tone_result = classifier(text, candidate_labels=config.CANDIDATE_TONES, multi_label=False)
    
    return {
        "Emotion": emotion_result['labels'][0].capitalize(),
        "Tone": tone_result['labels'][0].capitalize(),
        "Reaction": detect_reaction(text)
    }

