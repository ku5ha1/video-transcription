"""
File hashing utilities for deduplication
"""

import hashlib
from typing import BinaryIO
from app.core.logging import get_logger

logger = get_logger("utils.file_hash")

CHUNK_SIZE = 8192  # 8KB chunks for memory efficiency


def calculate_file_hash(file_data: bytes) -> str:
    """
    Calculate SHA-256 hash of file data

    Args:
        file_data: File content as bytes

    Returns:
        Hex digest of SHA-256 hash
    """
    try:
        sha256_hash = hashlib.sha256()
        sha256_hash.update(file_data)
        file_hash = sha256_hash.hexdigest()
        logger.debug(f"Calculated file hash: {file_hash[:16]}...")
        return file_hash
    except Exception as e:
        logger.error(f"Failed to calculate file hash: {e}")
        raise


def calculate_file_hash_streaming(file_stream: BinaryIO) -> str:
    """
    Calculate SHA-256 hash of file stream (memory efficient for large files)

    Args:
        file_stream: File-like object

    Returns:
        Hex digest of SHA-256 hash
    """
    try:
        sha256_hash = hashlib.sha256()

        # Read file in chunks
        while chunk := file_stream.read(CHUNK_SIZE):
            sha256_hash.update(chunk)

        file_hash = sha256_hash.hexdigest()
        logger.debug(f"Calculated file hash (streaming): {file_hash[:16]}...")
        return file_hash
    except Exception as e:
        logger.error(f"Failed to calculate file hash (streaming): {e}")
        raise
