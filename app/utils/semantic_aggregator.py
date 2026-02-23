"""
Semantic Aggregator for reconstructing sentence-level segments from word-level timestamps
"""
from typing import List, Dict, Any
from app.core.logging import get_logger

logger = get_logger("utils.semantic_aggregator")


class SemanticSegment:
    """Represents a semantic segment with word-level timing"""
    
    def __init__(self):
        self.words = []
        self.start_time = None
        self.end_time = None
        self.speaker = None
    
    def add_word(self, word: str, start: float, end: float):
        """Add a word to the segment"""
        if self.start_time is None:
            self.start_time = start
        self.end_time = end
        self.words.append(word)
    
    def get_text(self) -> str:
        """Get the full text of the segment"""
        return " ".join(self.words).strip()
    
    def get_length(self) -> int:
        """Get character length of the segment"""
        return len(self.get_text())
    
    def is_empty(self) -> bool:
        """Check if segment is empty"""
        return len(self.words) == 0
    
    def should_flush(self, min_length: int = 150) -> bool:
        """
        Check if segment should be flushed based on punctuation and length
        
        Args:
            min_length: Minimum character length before considering punctuation flush
        """
        if self.is_empty():
            return False
        
        text = self.get_text()
        
        # Check if last word ends with sentence-ending punctuation
        if text and text[-1] in '.!?':
            # Only flush if we have enough content
            if len(text) > min_length:
                return True
        
        return False


def get_speaker_at_time(timestamp: float, speaker_labels: List[Dict]) -> str:
    """
    Find which speaker is active at a given timestamp
    
    Args:
        timestamp: Time in seconds
        speaker_labels: List of speaker segments with start, end, and speaker fields
    
    Returns:
        Speaker ID or None
    """
    if not speaker_labels:
        return None
    
    for speaker_seg in speaker_labels:
        if speaker_seg["start"] <= timestamp <= speaker_seg["end"]:
            return speaker_seg["speaker"]
    
    return None


def reconstruct_semantic_segments(
    whisper_segments: List[Any],
    speaker_labels: List[Dict],
    min_flush_length: int = 150,
    max_segment_length: int = 500
) -> List[Dict]:
    """
    Reconstruct semantic segments from word-level timestamps
    
    Args:
        whisper_segments: Raw segments from Whisper with word-level timestamps
        speaker_labels: Speaker diarization results
        min_flush_length: Minimum character length before flushing on punctuation
        max_segment_length: Maximum character length before forcing a flush
    
    Returns:
        List of semantic segments with accurate timing and speaker info
    """
    logger.info("Starting semantic segment reconstruction")
    
    semantic_segments = []
    current_segment = SemanticSegment()
    current_speaker = None
    
    for whisper_seg in whisper_segments:
        # Check if segment has word-level timestamps
        if not hasattr(whisper_seg, 'words') or not whisper_seg.words:
            logger.warning(f"Segment has no word timestamps, using segment-level timing")
            # Fallback: treat entire segment as one unit
            text = whisper_seg.text.strip()
            if text:
                speaker = get_speaker_at_time(whisper_seg.start, speaker_labels)
                semantic_segments.append({
                    'text': text,
                    'start_time': whisper_seg.start,
                    'end_time': whisper_seg.end,
                    'speaker': speaker
                })
            continue
        
        # Process each word
        for word_info in whisper_seg.words:
            word_text = word_info.word.strip()
            word_start = word_info.start
            word_end = word_info.end
            
            # Determine speaker for this word
            word_speaker = get_speaker_at_time(word_start, speaker_labels)
            
            # Check if speaker changed
            if current_speaker is not None and word_speaker != current_speaker:
                # Flush current segment due to speaker change
                if not current_segment.is_empty():
                    logger.debug(f"Flushing segment due to speaker change: {current_speaker} -> {word_speaker}")
                    semantic_segments.append({
                        'text': current_segment.get_text(),
                        'start_time': current_segment.start_time,
                        'end_time': current_segment.end_time,
                        'speaker': current_speaker
                    })
                    current_segment = SemanticSegment()
            
            # Update current speaker
            current_speaker = word_speaker
            
            # Add word to current segment
            current_segment.add_word(word_text, word_start, word_end)
            
            # Check if we should flush based on punctuation and length
            if current_segment.should_flush(min_flush_length):
                logger.debug(f"Flushing segment due to punctuation: {current_segment.get_text()[:50]}...")
                semantic_segments.append({
                    'text': current_segment.get_text(),
                    'start_time': current_segment.start_time,
                    'end_time': current_segment.end_time,
                    'speaker': current_speaker
                })
                current_segment = SemanticSegment()
            
            # Force flush if segment is too long
            elif current_segment.get_length() > max_segment_length:
                logger.debug(f"Flushing segment due to max length: {current_segment.get_length()} chars")
                semantic_segments.append({
                    'text': current_segment.get_text(),
                    'start_time': current_segment.start_time,
                    'end_time': current_segment.end_time,
                    'speaker': current_speaker
                })
                current_segment = SemanticSegment()
    
    # Flush any remaining segment
    if not current_segment.is_empty():
        logger.debug("Flushing final segment")
        semantic_segments.append({
            'text': current_segment.get_text(),
            'start_time': current_segment.start_time,
            'end_time': current_segment.end_time,
            'speaker': current_speaker
        })
    
    logger.info(f"Reconstructed {len(semantic_segments)} semantic segments from word-level data")
    return semantic_segments
