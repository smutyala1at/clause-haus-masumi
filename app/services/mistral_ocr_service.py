"""
Mistral OCR Service
Handles batch OCR processing for PDFs with robust error handling,
rate limiting, and retry logic. Supports both base64-encoded PDFs
and uploaded PDFs via URLs.
"""

import asyncio
import base64
import logging
import time
from typing import List, Dict, Any, Optional, Union
from urllib.parse import urlparse

from mistralai import Mistral

from app.core.config import settings

logger = logging.getLogger(__name__)


class MistralOCRService:
    """
    Mistral OCR service with robust error handling, rate limiting, and retry logic.
    
    Features:
    - Automatic retry with exponential backoff for rate limits
    - Batch processing for multiple PDFs
    - Support for base64-encoded PDFs and uploaded PDF URLs
    - Simple, easy-to-modify interface
    """
    
    # Rate limit constants (requests per minute)
    # Mistral OCR typically allows 50-100 requests per minute
    DEFAULT_RPM = 50
    DEFAULT_TPM = 1000000  # Tokens per minute (if applicable)
    
    # Retry configuration
    MAX_RETRIES = 5
    INITIAL_RETRY_DELAY = 1.0  # seconds
    MAX_RETRY_DELAY = 60.0  # seconds
    BACKOFF_MULTIPLIER = 2.0
    
    # Batch configuration
    DEFAULT_BATCH_SIZE = 10  # Process 10 PDFs at a time
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Mistral OCR service.
        
        Args:
            api_key: Mistral API key (defaults to MISTRAL_API_KEY from settings)
        """
        self.api_key = api_key or settings.MISTRAL_API_KEY
        if not self.api_key:
            raise ValueError("Mistral API key is required. Set MISTRAL_API_KEY in environment variables.")
        
        self.client = Mistral(api_key=self.api_key)
        
        # Rate limiting tracking
        self._request_times: List[float] = []
        self._rate_limit_lock = asyncio.Lock()
    
    def _is_base64_pdf(self, value: str) -> bool:
        """
        Check if a value is a base64-encoded PDF.
        
        Args:
            value: String value to check
            
        Returns:
            True if value is base64 PDF, False otherwise
        """
        return value.startswith("data:application/pdf;base64,") or (
            len(value) > 100 and not value.startswith("http")
        )
    
    def _is_url(self, value: str) -> bool:
        """
        Check if a value is a URL.
        
        Args:
            value: String value to check
            
        Returns:
            True if value is a URL, False otherwise
        """
        try:
            result = urlparse(value)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def _extract_base64_content(self, value: str) -> str:
        """
        Extract base64 content from data URI or return as-is.
        
        Args:
            value: Base64 string, possibly with data URI prefix
            
        Returns:
            Base64 content without prefix
        """
        if value.startswith("data:application/pdf;base64,"):
            return value.split(",", 1)[1]
        return value
    
    async def _check_rate_limit(self) -> None:
        """
        Check if we're within rate limits and wait if necessary.
        """
        async with self._rate_limit_lock:
            now = time.time()
            # Remove requests older than 1 minute
            self._request_times = [t for t in self._request_times if now - t < 60]
            
            # If we're at the limit, wait until the oldest request is 1 minute old
            if len(self._request_times) >= self.DEFAULT_RPM:
                oldest_request = min(self._request_times)
                wait_time = 60 - (now - oldest_request) + 0.1  # Add small buffer
                if wait_time > 0:
                    logger.info(f"Rate limit reached. Waiting {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time)
                    # Clean up again after waiting
                    now = time.time()
                    self._request_times = [t for t in self._request_times if now - t < 60]
            
            # Record this request
            self._request_times.append(time.time())
    
    def _parse_error(self, error: Exception) -> Dict[str, Any]:
        """
        Parse error and extract useful information.
        
        Args:
            error: Exception to parse
            
        Returns:
            Dictionary with error information
        """
        error_str = str(error).lower()
        
        # Check for rate limit errors
        if "rate limit" in error_str or "429" in error_str:
            return {
                "error_type": "rate_limit",
                "retryable": True,
                "retry_after": self.INITIAL_RETRY_DELAY * 2
            }
        
        # Check for authentication errors
        if "unauthorized" in error_str or "401" in error_str or "403" in error_str:
            return {
                "error_type": "authentication",
                "retryable": False
            }
        
        # Check for invalid request errors
        if "invalid" in error_str or "400" in error_str:
            return {
                "error_type": "invalid_request",
                "retryable": False
            }
        
        # Default to retryable error
        return {
            "error_type": "unknown",
            "retryable": True
        }
    
    async def _retry_with_backoff(self, func, *args, **kwargs):
        """
        Execute function with exponential backoff retry logic.
        
        Args:
            func: Function to execute (can be sync or async)
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            Result from function
            
        Raises:
            Exception: If all retries fail
        """
        delay = self.INITIAL_RETRY_DELAY
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                # Check rate limit before each attempt
                await self._check_rate_limit()
                
                # Execute function (handle both sync and async)
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                return result
                
            except Exception as e:
                last_error = e
                parsed_error = self._parse_error(e)
                
                # Don't retry on certain errors
                if not parsed_error.get("retryable", True):
                    logger.error(f"Non-retryable error: {str(e)}")
                    raise
                
                # Check if we should retry
                if attempt < self.MAX_RETRIES - 1:
                    # Use retry_after from error if available
                    if parsed_error.get("retry_after"):
                        delay = min(parsed_error["retry_after"], self.MAX_RETRY_DELAY)
                    else:
                        delay = min(delay * self.BACKOFF_MULTIPLIER, self.MAX_RETRY_DELAY)
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{self.MAX_RETRIES} failed: {str(e)[:100]}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All retries exhausted. Last error: {str(e)}")
                    raise
        
        # Should never reach here, but just in case
        raise last_error or Exception("Unknown error")
    
    def _process_base64_pdf(self, base64_content: str) -> Dict[str, Any]:
        """
        Process a base64-encoded PDF with OCR.
        
        Args:
            base64_content: Base64-encoded PDF content
            
        Returns:
            OCR response dictionary
        """
        document = {
            "type": "document_url",
            "document_url": f"data:application/pdf;base64,{base64_content}"
        }
        
        response = self.client.ocr.process(
            model="mistral-ocr-latest",
            document=document,
            include_image_base64=True
        )
        
        return response
    
    def _process_url_pdf(self, url: str) -> Dict[str, Any]:
        """
        Process a PDF from URL with OCR.
        
        Args:
            url: URL to the PDF file
            
        Returns:
            OCR response dictionary
        """
        document = {
            "type": "document_url",
            "document_url": url
        }
        
        response = self.client.ocr.process(
            model="mistral-ocr-latest",
            document=document,
            include_image_base64=True
        )
        
        return response
    
    def _upload_and_process_pdf(self, pdf_content: bytes, file_name: str = "document.pdf") -> Dict[str, Any]:
        """
        Upload a PDF to Mistral and process it with OCR.
        
        Args:
            pdf_content: PDF file content as bytes
            file_name: Name of the file
            
        Returns:
            OCR response dictionary
        """
        # Upload file to Mistral
        uploaded_file = self.client.files.upload(
            file={
                "file_name": file_name,
                "content": pdf_content,
            },
            purpose="ocr"
        )
        
        # Get signed URL (may be in signed_url attribute or need to fetch separately)
        signed_url = None
        if hasattr(uploaded_file, 'signed_url') and uploaded_file.signed_url:
            signed_url = uploaded_file.signed_url
        elif hasattr(uploaded_file, 'id'):
            # If signed_url not available, get it separately
            signed_url_response = self.client.files.get_signed_url(
                file_id=uploaded_file.id,
                expiry=24  # 24 hours
            )
            signed_url = signed_url_response.url if hasattr(signed_url_response, 'url') else str(signed_url_response)
        else:
            raise ValueError("Could not get signed URL from uploaded file")
        
        # Process with OCR using the signed URL
        document = {
            "type": "document_url",
            "document_url": signed_url
        }
        
        response = self.client.ocr.process(
            model="mistral-ocr-latest",
            document=document,
            include_image_base64=True
        )
        
        return response
    
    async def process_pdf(
        self,
        pdf_input: Union[str, bytes],
        file_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a single PDF with OCR.
        Automatically detects if input is base64, URL, or bytes.
        
        Args:
            pdf_input: PDF as base64 string, URL string, or bytes
            file_name: Optional file name (required if pdf_input is bytes)
            
        Returns:
            OCR response dictionary
            
        Raises:
            ValueError: If input format is invalid
            Exception: If OCR processing fails after retries
        """
        # Handle bytes input
        if isinstance(pdf_input, bytes):
            if not file_name:
                file_name = "document.pdf"
            return await self._retry_with_backoff(
                self._upload_and_process_pdf,
                pdf_input,
                file_name
            )
        
        # Handle string input
        if not isinstance(pdf_input, str):
            raise ValueError(f"Invalid input type: {type(pdf_input)}. Expected str or bytes.")
        
        # Check if it's a base64 PDF
        if self._is_base64_pdf(pdf_input):
            base64_content = self._extract_base64_content(pdf_input)
            return await self._retry_with_backoff(
                self._process_base64_pdf,
                base64_content
            )
        
        # Check if it's a URL
        if self._is_url(pdf_input):
            return await self._retry_with_backoff(
                self._process_url_pdf,
                pdf_input
            )
        
        # Try to decode as base64 if it looks like base64
        try:
            # Validate it's valid base64
            base64.b64decode(pdf_input, validate=True)
            return await self._retry_with_backoff(
                self._process_base64_pdf,
                pdf_input
            )
        except Exception:
            pass
        
        raise ValueError(
            f"Invalid PDF input format. Expected base64 string, URL, or bytes. "
            f"Got: {pdf_input[:100]}..."
        )
    
    async def process_pdfs_batch(
        self,
        pdf_inputs: List[Union[str, bytes]],
        file_names: Optional[List[str]] = None,
        batch_size: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Process multiple PDFs with OCR in batches.
        
        Args:
            pdf_inputs: List of PDFs (base64 strings, URLs, or bytes)
            file_names: Optional list of file names (required if any input is bytes)
            batch_size: Number of PDFs to process per batch (default: DEFAULT_BATCH_SIZE)
            
        Returns:
            List of OCR response dictionaries (one per PDF)
            
        Raises:
            ValueError: If inputs are invalid
        """
        if not pdf_inputs:
            raise ValueError("At least one PDF input is required")
        
        if batch_size is None:
            batch_size = self.DEFAULT_BATCH_SIZE
        
        if file_names is None:
            file_names = [None] * len(pdf_inputs)
        
        if len(file_names) != len(pdf_inputs):
            raise ValueError("file_names length must match pdf_inputs length")
        
        results = []
        
        # Process in batches
        for i in range(0, len(pdf_inputs), batch_size):
            batch = pdf_inputs[i:i + batch_size]
            batch_names = file_names[i:i + batch_size]
            
            logger.info(f"Processing batch {i // batch_size + 1} ({len(batch)} PDFs)...")
            
            # Process batch concurrently (with rate limiting handled internally)
            batch_tasks = [
                self.process_pdf(pdf_input, file_name)
                for pdf_input, file_name in zip(batch, batch_names)
            ]
            
            try:
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                # Handle results and exceptions
                for j, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        logger.error(f"Error processing PDF {i + j}: {str(result)}")
                        results.append({
                            "error": str(result),
                            "index": i + j
                        })
                    else:
                        results.append(result)
                        
            except Exception as e:
                logger.error(f"Error processing batch {i // batch_size + 1}: {str(e)}")
                # Add error entries for all items in failed batch
                for j in range(len(batch)):
                    results.append({
                        "error": str(e),
                        "index": i + j
                    })
        
        return results

