#!/usr/bin/env python3
import argparse
import os
import tarfile
from urllib.request import urlretrieve

from huggingface_hub import login
from transformers import (
    AutoTokenizer,
    AutoModel,
    AutoModelForSequenceClassification,
    Wav2Vec2Processor,
    Wav2Vec2ForSequenceClassification,
)

print("=" * 80)
print("Downloading AI Models to Persistent Volumes")
print("=" * 80)

parser = argparse.ArgumentParser(description="Download app models")
parser.add_argument("--hf-token", default=None, help="Hugging Face token")
args = parser.parse_args()

# Keep model caches in mounted persistent directories
emotion_cache_dir = "/app/models/emotion"
tone_cache_dir = "/app/models/tone"
qdrant_cache_dir = "/app/models/qdrant"
sherpa_cache_dir = "/app/models/sherpa"

for model_dir in [emotion_cache_dir, tone_cache_dir, qdrant_cache_dir, sherpa_cache_dir]:
    os.makedirs(model_dir, exist_ok=True)

# Get Hugging Face token from CLI first, then env
huggingface_token = args.hf_token or os.getenv("HUGGING_FACE_TOKEN")
if huggingface_token:
    print("Using Hugging Face token for authenticated downloads")
    login(token=huggingface_token, add_to_git_credential=False)
else:
    print("Warning: HUGGING_FACE_TOKEN not set, using anonymous access")

# Model configurations
models_to_download = [
    {
        "name": "Audio Emotion Recognition (Wav2Vec2)",
        "model_id": "Dpngtm/wav2vec2-emotion-recognition",
        "type": "wav2vec2",
        "cache_dir": emotion_cache_dir,
    },
    {
        "name": "Text Tone Classification (DeBERTa)",
        "model_id": "cross-encoder/nli-deberta-v3-small",
        "type": "sequence_classification",
        "cache_dir": tone_cache_dir,
    },
    {
        "name": "Sentence Embeddings (for Qdrant)",
        "model_id": "sentence-transformers/all-MiniLM-L6-v2",
        "type": "sentence_transformer",
        "cache_dir": qdrant_cache_dir,
    },
]


def download_wav2vec2_model(model_id, cache_dir, token=None):
    """Download Wav2Vec2 model and processor"""
    print("  Downloading processor...")
    Wav2Vec2Processor.from_pretrained(model_id, cache_dir=cache_dir, token=token)
    print("  Downloading model...")
    Wav2Vec2ForSequenceClassification.from_pretrained(
        model_id, cache_dir=cache_dir, token=token
    )
    print("  ✓ Downloaded successfully")


def download_sequence_classification_model(model_id, cache_dir, token=None):
    """Download sequence classification model and tokenizer"""
    print("  Downloading tokenizer...")
    AutoTokenizer.from_pretrained(model_id, cache_dir=cache_dir, token=token)
    print("  Downloading model...")
    AutoModelForSequenceClassification.from_pretrained(
        model_id, cache_dir=cache_dir, token=token
    )
    print("  ✓ Downloaded successfully")


def download_sentence_transformer_model(model_id, cache_dir, token=None):
    """Download sentence transformer model and tokenizer"""
    print("  Downloading tokenizer...")
    AutoTokenizer.from_pretrained(model_id, cache_dir=cache_dir, token=token)
    print("  Downloading model...")
    AutoModel.from_pretrained(model_id, cache_dir=cache_dir, token=token)
    print("  ✓ Downloaded successfully")


def download_sherpa_models(target_dir):
    """Download Sherpa-ONNX diarization models expected by DiarizationService."""
    seg_model = os.path.join(
        target_dir, "sherpa-onnx-pyannote-segmentation-3-0", "model.onnx"
    )
    emb_model = os.path.join(target_dir, "nemo_en_titanet_small.onnx")

    if not os.path.exists(seg_model):
        print("\n[Sherpa-ONNX Segmentation]")
        archive_name = "sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"
        archive_path = os.path.join(target_dir, archive_name)
        seg_url = (
            "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
            "speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"
        )
        print(f"  Downloading from: {seg_url}")
        urlretrieve(seg_url, archive_path)
        with tarfile.open(archive_path, "r:bz2") as tar:
            tar.extractall(path=target_dir)
        os.remove(archive_path)
        print("  ✓ Segmentation model downloaded")
    else:
        print("\n[Sherpa-ONNX Segmentation]")
        print("  ✓ Already present, skipping")

    if not os.path.exists(emb_model):
        print("\n[Sherpa-ONNX Embedding]")
        emb_url = (
            "https://github.com/k2-fsa/sherpa-onnx/releases/download/"
            "speaker-recongition-models/nemo_en_titanet_small.onnx"
        )
        print(f"  Downloading from: {emb_url}")
        urlretrieve(emb_url, emb_model)
        print("  ✓ Embedding model downloaded")
    else:
        print("\n[Sherpa-ONNX Embedding]")
        print("  ✓ Already present, skipping")


# Download all Hugging Face models
for model_config in models_to_download:
    print(f"\n[{model_config['name']}]")
    print(f"  Model ID: {model_config['model_id']}")

    try:
        if model_config["type"] == "wav2vec2":
            download_wav2vec2_model(
                model_config["model_id"], model_config["cache_dir"], huggingface_token
            )
        elif model_config["type"] == "sequence_classification":
            download_sequence_classification_model(
                model_config["model_id"], model_config["cache_dir"], huggingface_token
            )
        elif model_config["type"] == "sentence_transformer":
            download_sentence_transformer_model(
                model_config["model_id"], model_config["cache_dir"], huggingface_token
            )
    except Exception as e:
        print(f"  ✗ Error downloading: {e}")
        raise

download_sherpa_models(sherpa_cache_dir)

print("\n" + "=" * 80)
print("All models downloaded successfully!")
print("=" * 80)

# Note: Whisper model (faster-whisper) is downloaded separately by the application
# as it uses CTranslate2 format, not standard Hugging Face transformers
print("\nNote: Whisper model (faster-whisper) will be downloaded on first use")
print("      It uses CTranslate2 format and has its own caching mechanism")
