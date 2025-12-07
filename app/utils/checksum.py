"""
Checksum utility functions
"""

import hashlib
from typing import Union


def calculate_checksum(text: str) -> str:
    """
    Calculate SHA256 checksum of text.
    
    Args:
        text: Text to hash
        
    Returns:
        Hexadecimal SHA256 hash
    """
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def calculate_pdf_checksum(pdf_input: Union[str, bytes]) -> str:
    """
    Calculate SHA256 checksum of PDF input.
    Handles base64 strings, URLs, and raw bytes.
    
    Args:
        pdf_input: PDF as base64 string, URL string, or bytes
        
    Returns:
        Hexadecimal SHA256 hash
    """
    if isinstance(pdf_input, bytes):
        return hashlib.sha256(pdf_input).hexdigest()
    
    if isinstance(pdf_input, str):
        # For base64, use the actual content (after data:application/pdf;base64,)
        if pdf_input.startswith("data:application/pdf;base64,"):
            # Use the full string including the data URI prefix for consistency
            return hashlib.sha256(pdf_input.encode('utf-8')).hexdigest()
        # For URLs, use the URL string
        elif pdf_input.startswith(("http://", "https://")):
            return hashlib.sha256(pdf_input.encode('utf-8')).hexdigest()
        # For other strings, treat as text
        else:
            return hashlib.sha256(pdf_input.encode('utf-8')).hexdigest()
    
    raise ValueError(f"Unsupported PDF input type: {type(pdf_input)}")

