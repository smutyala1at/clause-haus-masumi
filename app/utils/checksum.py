"""
Checksum utility functions
"""

import hashlib


def calculate_checksum(text: str) -> str:
    """
    Calculate SHA256 checksum of text.
    
    Args:
        text: Text to hash
        
    Returns:
        Hexadecimal SHA256 hash
    """
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

