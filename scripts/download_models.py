#!/usr/bin/env python3
"""
Pre-download all AI models to Docker build cache
This script downloads models during Docker build to leverage BuildKit cache mounts
"""
import os
from transformers import AutoTokenizer, AutoModel, AutoModelForSequenceClassification, Wav2Vec2Processor, Wav2Vec2ForSequenceClassification

print("=" * 80)
print("Downloading AI Models to Cache")
print("=" * 80)

# Set cache directory
cache_dir = os.getenv("HF_HOME", "/root/.cache/huggingface")
print(f"Cache directory: {cache_dir}\n")

# Model configurations
models_to_download = [
    {
        "name": "Audio Emotion Recognition (Wav2Vec2)",
        "model_id": "Dpngtm/wav2vec2-emotion-recognition",
        "type": "wav2vec2"
    },
    {
        "name": "Text Tone Classification (DeBERTa)",
        "model_id": "cross-encoder/nli-deberta-v3-small",
        "type": "sequence_classification"
    },
    {
        "name": "Sentence Embeddings (for Qdrant)",
        "model_id": "sentence-transformers/all-MiniLM-L6-v2",
        "type": "sentence_transformer"
    }
]

def download_wav2vec2_model(model_id, cache_dir):
    """Download Wav2Vec2 model and processor"""
    print(f"  Downloading processor...")
    processor = Wav2Vec2Processor.from_pretrained(
        model_id,
        cache_dir=cache_dir
    )
    print(f"  Downloading model...")
    model = Wav2Vec2ForSequenceClassification.from_pretrained(
        model_id,
        cache_dir=cache_dir
    )
    print(f"  ✓ Downloaded successfully")

def download_sequence_classification_model(model_id, cache_dir):
    """Download sequence classification model and tokenizer"""
    print(f"  Downloading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(
        model_id,
        cache_dir=cache_dir
    )
    print(f"  Downloading model...")
    model = AutoModelForSequenceClassification.from_pretrained(
        model_id,
        cache_dir=cache_dir
    )
    print(f"  ✓ Downloaded successfully")

def download_sentence_transformer_model(model_id, cache_dir):
    """Download sentence transformer model and tokenizer"""
    print(f"  Downloading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(
        model_id,
        cache_dir=cache_dir
    )
    print(f"  Downloading model...")
    model = AutoModel.from_pretrained(
        model_id,
        cache_dir=cache_dir
    )
    print(f"  ✓ Downloaded successfully")

# Download all models
for model_config in models_to_download:
    print(f"\n[{model_config['name']}]")
    print(f"  Model ID: {model_config['model_id']}")
    
    try:
        if model_config['type'] == 'wav2vec2':
            download_wav2vec2_model(model_config['model_id'], cache_dir)
        elif model_config['type'] == 'sequence_classification':
            download_sequence_classification_model(model_config['model_id'], cache_dir)
        elif model_config['type'] == 'sentence_transformer':
            download_sentence_transformer_model(model_config['model_id'], cache_dir)
    except Exception as e:
        print(f"  ✗ Error downloading: {e}")
        raise

print("\n" + "=" * 80)
print("All models downloaded successfully!")
print("=" * 80)

# Note: Whisper model (faster-whisper) is downloaded separately by the application
# as it uses CTranslate2 format, not standard Hugging Face transformers
print("\nNote: Whisper model (faster-whisper) will be downloaded on first use")
print("      It uses CTranslate2 format and has its own caching mechanism")
