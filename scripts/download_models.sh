#!/bin/bash
set -e

echo "Creating model directories..."
mkdir -p /app/models/sherpa
mkdir -p /app/models/whisper
mkdir -p /app/models/emotion
mkdir -p /app/models/tone

echo "=== Downloading Sherpa-ONNX Models ==="
cd /app/models/sherpa

echo "Downloading Sherpa-ONNX Segmentation Model..."
wget -q --show-progress https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2

echo "Extracting Segmentation Model..."
tar -xjf sherpa-onnx-pyannote-segmentation-3-0.tar.bz2

echo "Cleaning up archive..."
rm sherpa-onnx-pyannote-segmentation-3-0.tar.bz2

echo "Downloading Speaker Embedding Model..."
wget -q --show-progress https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx

echo "Sherpa-ONNX models downloaded successfully!"
ls -lh /app/models/sherpa/

echo ""
echo "=== Pre-downloading Enhanced NLP Models ==="
cd /app

# Download Audio Emotion Model (Wav2Vec2)
echo "Downloading Audio Emotion Model (Dpngtm/wav2vec2-emotion-recognition)..."
python3 -c "
from transformers import AutoModelForAudioClassification, AutoFeatureExtractor
model = AutoModelForAudioClassification.from_pretrained('Dpngtm/wav2vec2-emotion-recognition', cache_dir='/app/models/emotion')
extractor = AutoFeatureExtractor.from_pretrained('Dpngtm/wav2vec2-emotion-recognition', cache_dir='/app/models/emotion')
print('Audio Emotion Model downloaded successfully!')
"

# Download Text Tone Model (DeBERTa)
echo "Downloading Text Tone Model (cross-encoder/nli-deberta-v3-small)..."
python3 -c "
from transformers import AutoModelForSequenceClassification, AutoTokenizer
model = AutoModelForSequenceClassification.from_pretrained('cross-encoder/nli-deberta-v3-small', cache_dir='/app/models/tone')
tokenizer = AutoTokenizer.from_pretrained('cross-encoder/nli-deberta-v3-small', cache_dir='/app/models/tone')
print('Text Tone Model downloaded successfully!')
"

echo ""
echo "=== Whisper Model ==="
echo "Note: Whisper large-v3-turbo model will be downloaded on first use (~1.5GB)"
echo "Model cache directory: /app/models/whisper"

echo ""
echo "All models setup complete!"


