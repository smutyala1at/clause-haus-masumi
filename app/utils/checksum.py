"""
Checksum utility functions
"""

import base64
import hashlib
import logging
from typing import Union

import httpx

logger = logging.getLogger(__name__)


def calculate_checksum(text: str) -> str:
    """
    Calculate SHA256 checksum of text.
    
    Args:
        text: Text to hash
        
    Returns:
        Hexadecimal SHA256 hash
    """
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


async def calculate_pdf_checksum(pdf_input: Union[str, bytes]) -> str:
    """
    Calculate SHA256 checksum of PDF input based on actual PDF content.
    Handles base64 strings, URLs, and raw bytes.
    
    For URLs: Downloads the PDF and hashes the content (ensures same PDF = same checksum regardless of URL)
    For base64: Decodes and hashes the actual PDF bytes
    For bytes: Hashes the bytes directly
    
    Args:
        pdf_input: PDF as base64 string, URL string, or bytes
        
    Returns:
        Hexadecimal SHA256 hash of the PDF content
    """
    if isinstance(pdf_input, bytes):
        return hashlib.sha256(pdf_input).hexdigest()
    
    if isinstance(pdf_input, str):
        # For base64, decode and hash the actual PDF content
        if pdf_input.startswith("data:application/pdf;base64,"):
            try:
                # Extract base64 content (after the comma)
                base64_content = pdf_input.split(",", 1)[1]
                # Decode to get actual PDF bytes
                pdf_bytes = base64.b64decode(base64_content)
                return hashlib.sha256(pdf_bytes).hexdigest()
            except Exception as e:
                logger.warning(f"Failed to decode base64 PDF for checksum: {e}. Falling back to string hash.")
                return hashlib.sha256(pdf_input.encode('utf-8')).hexdigest()
        
        # For URLs, download and hash the actual PDF content
        elif pdf_input.startswith(("http://", "https://")):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(pdf_input)
                    response.raise_for_status()
                    pdf_bytes = response.content
                    return hashlib.sha256(pdf_bytes).hexdigest()
            except Exception as e:
                logger.warning(f"Failed to download PDF from URL for checksum: {e}. Falling back to URL string hash.")
                # Fallback: hash the URL string if download fails
                return hashlib.sha256(pdf_input.encode('utf-8')).hexdigest()
        
        # For other strings, treat as text
        else:
            return hashlib.sha256(pdf_input.encode('utf-8')).hexdigest()
    
    raise ValueError(f"Unsupported PDF input type: {type(pdf_input)}")

