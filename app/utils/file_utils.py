import os
import tempfile
from typing import Optional

def create_temp_file(suffix: str = '.tmp') -> str:
    """Create a temporary file and return its path"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_file.close()
    return temp_file.name

def cleanup_file(file_path: str) -> None:
    """Safely remove a file if it exists"""
    if os.path.exists(file_path):
        os.unlink(file_path)

def ensure_directory(directory: str) -> None:
    """Create directory if it doesn't exist"""
    if not os.path.exists(directory):
        os.makedirs(directory)