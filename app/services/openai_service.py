"""
OpenAI Service
Handles batch embeddings and chat completions with robust error handling,
rate limiting, and token management.
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, Union

import httpx
from openai import OpenAI, AsyncOpenAI
from openai.types import Embedding
from openai import RateLimitError, APIError

from app.core.config import settings
from app.schemas.openai import (
    OpenAIError,
    OpenAIErrorType,
    EmbeddingRequest,
    ChatMessage,
    ChatRequest,
    EmbeddingResponse,
    ChatResponse
)

logger = logging.getLogger(__name__)


class OpenAIService:
    """
    OpenAI service with robust error handling, rate limiting, and token management.
    
    Features:
    - Automatic retry with exponential backoff for rate limits
    - Token counting and validation before requests
    - Comprehensive error handling
    - Batch embedding support
    - Simple, easy-to-modify interface
    """
    
    # Rate limit constants (requests per minute)
    RATE_LIMITS = {
        "gpt-4o": {"rpm": 5000, "tpm": 10000000},
        "gpt-4o-mini": {"rpm": 5000, "tpm": 10000000},
        "gpt-4": {"rpm": 500, "tpm": 10000},
        "gpt-3.5-turbo": {"rpm": 5000, "tpm": 1000000},
        "text-embedding-3-small": {"rpm": 5000, "tpm": 1000000},
        "text-embedding-3-large": {"rpm": 5000, "tpm": 1000000},
        "text-embedding-ada-002": {"rpm": 5000, "tpm": 1000000},
    }
    
    # Default limits if model not found
    DEFAULT_RPM = 5000
    DEFAULT_TPM = 1000000
    
    # Retry configuration
    MAX_RETRIES = 5
    INITIAL_RETRY_DELAY = 1.0  # seconds
    MAX_RETRY_DELAY = 60.0  # seconds
    BACKOFF_MULTIPLIER = 2.0
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize OpenAI service.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY from settings)
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY in environment variables.")
        
        self.client = AsyncOpenAI(api_key=self.api_key, timeout=60.0)
        self.sync_client = OpenAI(api_key=self.api_key, timeout=60.0)
        
        # Rate limiting tracking
        self._request_times: Dict[str, List[float]] = {}
        self._token_usage: Dict[str, int] = {}
        self._rate_limit_lock = asyncio.Lock()
    
    def _get_rate_limits(self, model: str) -> Dict[str, int]:
        """Get rate limits for a model"""
        return self.RATE_LIMITS.get(model, {
            "rpm": self.DEFAULT_RPM,
            "tpm": self.DEFAULT_TPM
        })
    
    async def _check_rate_limit(self, model: str, estimated_tokens: int = 0) -> None:
        """
        Check if we're within rate limits for the model.
        
        Args:
            model: Model name
            estimated_tokens: Estimated tokens for this request
            
        Raises:
            OpenAIError: If rate limit would be exceeded
        """
        async with self._rate_limit_lock:
            limits = self._get_rate_limits(model)
            now = time.time()
            
            # Clean old request times (older than 1 minute)
            if model not in self._request_times:
                self._request_times[model] = []
            self._request_times[model] = [
                t for t in self._request_times[model] 
                if now - t < 60.0
            ]
            
            # Check RPM
            if len(self._request_times[model]) >= limits["rpm"]:
                oldest_request = min(self._request_times[model])
                wait_time = 60.0 - (now - oldest_request) + 1.0
                raise OpenAIError(
                    f"Rate limit exceeded for {model}. {limits['rpm']} requests per minute limit.",
                    OpenAIErrorType.RATE_LIMIT,
                    retry_after=wait_time
                )
            
            # Check TPM
            current_tokens = self._token_usage.get(model, 0)
            if current_tokens + estimated_tokens > limits["tpm"]:
                # Reset token usage after 1 minute
                wait_time = 60.0 + 1.0
                raise OpenAIError(
                    f"Token limit exceeded for {model}. {limits['tpm']} tokens per minute limit.",
                    OpenAIErrorType.TOKEN_LIMIT,
                    retry_after=wait_time
                )
    
    async def _record_request(self, model: str, tokens_used: int) -> None:
        """Record a request for rate limiting"""
        async with self._rate_limit_lock:
            now = time.time()
            if model not in self._request_times:
                self._request_times[model] = []
            self._request_times[model].append(now)
            self._token_usage[model] = self._token_usage.get(model, 0) + tokens_used
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Rough token estimation (4 characters ≈ 1 token).
        For accurate counting, use tiktoken library.
        """
        return len(text) // 4
    
    def _parse_error(self, error: Exception) -> OpenAIError:
        """
        Parse OpenAI API error and return appropriate OpenAIError.
        
        Args:
            error: Exception from OpenAI API
            
        Returns:
            OpenAIError with appropriate error type
        """
        error_str = str(error).lower()
        
        # Rate limit errors - OpenAI SDK provides RateLimitError
        if isinstance(error, RateLimitError) or "rate limit" in error_str or "429" in error_str:
            retry_after = None
            
            # Try multiple ways to get retry_after from the error
            # Note: OpenAI API sends Retry-After header, but SDK may not always expose it
            # Method 1: From RateLimitError.response.headers (most common)
            if isinstance(error, RateLimitError):
                if hasattr(error, 'response') and error.response:
                    # Try to get headers from response
                    headers = None
                    if hasattr(error.response, 'headers'):
                        headers = error.response.headers
                    elif hasattr(error.response, 'get'):
                        # If response is a dict-like object
                        headers = error.response
                    
                    if headers:
                        retry_after_header = headers.get("retry-after") or headers.get("Retry-After")
                        if retry_after_header:
                            try:
                                retry_after = float(retry_after_header)
                                logger.debug(f"Extracted retry_after from RateLimitError: {retry_after}s")
                            except (ValueError, TypeError):
                                pass
                
                # Method 1b: Check if error has retry_after attribute directly
                if retry_after is None and hasattr(error, 'retry_after'):
                    try:
                        retry_after = float(error.retry_after)
                        logger.debug(f"Extracted retry_after from error.retry_after: {retry_after}s")
                    except (ValueError, TypeError):
                        pass
            
            # Method 2: From APIError (RateLimitError inherits from APIError)
            if retry_after is None and isinstance(error, APIError):
                if hasattr(error, 'response') and error.response:
                    headers = None
                    if hasattr(error.response, 'headers'):
                        headers = error.response.headers
                    elif hasattr(error.response, 'get'):
                        headers = error.response
                    
                    if headers:
                        retry_after_header = headers.get("retry-after") or headers.get("Retry-After")
                        if retry_after_header:
                            try:
                                retry_after = float(retry_after_header)
                                logger.debug(f"Extracted retry_after from APIError: {retry_after}s")
                            except (ValueError, TypeError):
                                pass
            
            # Method 3: From httpx response (if error wraps httpx response)
            if retry_after is None and hasattr(error, 'response'):
                response = error.response
                if response:
                    headers = None
                    if hasattr(response, 'headers'):
                        headers = response.headers
                    elif isinstance(response, dict):
                        headers = response
                    
                    if headers:
                        retry_after_header = headers.get("retry-after") or headers.get("Retry-After")
                        if retry_after_header:
                            try:
                                retry_after = float(retry_after_header)
                                logger.debug(f"Extracted retry_after from response: {retry_after}s")
                            except (ValueError, TypeError):
                                pass
            
            # Log if we couldn't extract retry_after
            if retry_after is None:
                logger.warning(
                    f"Rate limit error encountered but retry_after not found in error. "
                    f"Error type: {type(error)}, Error: {str(error)[:200]}. "
                    f"Will use exponential backoff instead."
                )
            
            return OpenAIError(
                f"Rate limit exceeded: {str(error)}",
                OpenAIErrorType.RATE_LIMIT,
                retry_after=retry_after
            )
        
        # Token limit errors
        if "token" in error_str and ("limit" in error_str or "exceeded" in error_str):
            return OpenAIError(
                f"Token limit exceeded: {str(error)}",
                OpenAIErrorType.TOKEN_LIMIT
            )
        
        # Authentication errors
        if "401" in error_str or "unauthorized" in error_str or "invalid api key" in error_str:
            return OpenAIError(
                f"Authentication failed: {str(error)}",
                OpenAIErrorType.AUTHENTICATION
            )
        
        # Permission errors
        if "403" in error_str or "permission" in error_str or "forbidden" in error_str:
            return OpenAIError(
                f"Permission denied: {str(error)}",
                OpenAIErrorType.PERMISSION
            )
        
        # Invalid request errors
        if "400" in error_str or "invalid" in error_str:
            return OpenAIError(
                f"Invalid request: {str(error)}",
                OpenAIErrorType.INVALID_REQUEST
            )
        
        # Server errors
        if "500" in error_str or "502" in error_str or "503" in error_str or "504" in error_str:
            return OpenAIError(
                f"OpenAI server error: {str(error)}",
                OpenAIErrorType.SERVER_ERROR
            )
        
        # Network errors
        if isinstance(error, (httpx.TimeoutException, httpx.NetworkError, ConnectionError)):
            return OpenAIError(
                f"Network error: {str(error)}",
                OpenAIErrorType.NETWORK
            )
        
        # Unknown error
        return OpenAIError(
            f"Unknown error: {str(error)}",
            OpenAIErrorType.UNKNOWN
        )
    
    async def _retry_with_backoff(self, func, *args, **kwargs):
        """
        Execute function with exponential backoff retry logic.
        
        Note on retry_after:
        - OpenAI API sends a Retry-After header with 429 errors
        - We try to extract it from the error, but SDK may not always expose it
        - If retry_after is available, we use it; otherwise fall back to exponential backoff
        
        Args:
            func: Async function to execute
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            Result from function
            
        Raises:
            OpenAIError: If all retries fail
        """
        delay = self.INITIAL_RETRY_DELAY
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                parsed_error = self._parse_error(e)
                
                # Don't retry on certain errors
                if parsed_error.error_type in [
                    OpenAIErrorType.AUTHENTICATION,
                    OpenAIErrorType.PERMISSION,
                    OpenAIErrorType.INVALID_REQUEST,
                    OpenAIErrorType.TOKEN_LIMIT
                ]:
                    raise parsed_error
                
                # Check if we should retry
                if attempt < self.MAX_RETRIES - 1:
                    # Use retry_after from error if available (from Retry-After header)
                    # Otherwise use exponential backoff
                    if parsed_error.retry_after:
                        delay = min(parsed_error.retry_after, self.MAX_RETRY_DELAY)
                        logger.info(
                            f"Using retry_after from API: {delay:.2f}s "
                            f"(attempt {attempt + 1}/{self.MAX_RETRIES})"
                        )
                    else:
                        delay = min(delay * self.BACKOFF_MULTIPLIER, self.MAX_RETRY_DELAY)
                        logger.warning(
                            f"Attempt {attempt + 1}/{self.MAX_RETRIES} failed: {str(e)[:100]}. "
                            f"Retrying in {delay:.2f}s (exponential backoff, retry_after not available)..."
                        )
                    await asyncio.sleep(delay)
                else:
                    raise parsed_error
        
        # Should never reach here, but just in case
        raise last_error or OpenAIError("Unknown error", OpenAIErrorType.UNKNOWN)
    
    async def create_embeddings(
        self,
        texts: Union[str, List[str]],
        model: str = "text-embedding-3-small",
        batch_size: int = 100
    ) -> List[Embedding]:
        """
        Create embeddings for text(s) with automatic batching and error handling.
        
        Args:
            texts: Single text string or list of texts
            model: Embedding model to use
            batch_size: Number of texts to process per batch
            
        Returns:
            List of Embedding objects
            
        Raises:
            OpenAIError: If request fails after retries
        """
        # Normalize input
        if isinstance(texts, str):
            texts = [texts]
        
        if not texts:
            raise ValueError("At least one text is required")
        
        # Validate texts
        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise ValueError(f"Text at index {i} is empty")
        
        all_embeddings = []
        
        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            logger.info(f"Processing embedding batch {i // batch_size + 1} ({len(batch)} texts)")
            
            # Estimate tokens
            total_tokens = sum(self._estimate_tokens(text) for text in batch)
            
            # Check rate limits
            await self._check_rate_limit(model, estimated_tokens=total_tokens)
            
            # Create embeddings with retry
            async def _create_batch():
                try:
                    response = await self.client.embeddings.create(
                        model=model,
                        input=batch
                    )
                    return response.data
                except Exception as e:
                    raise self._parse_error(e)
            
            try:
                embeddings = await self._retry_with_backoff(_create_batch)
                all_embeddings.extend(embeddings)
                
                # Record request (estimate tokens used)
                await self._record_request(model, total_tokens)
                
                # Small delay between batches to avoid hitting rate limits
                if i + batch_size < len(texts):
                    await asyncio.sleep(0.1)
                    
            except OpenAIError as e:
                logger.error(f"Failed to create embeddings for batch: {e.message}")
                raise
        
        logger.info(f"Successfully created {len(all_embeddings)} embeddings")
        return all_embeddings
    
    async def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> Any:
        """
        Create chat completion with error handling and rate limiting.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Chat model to use
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response
            stream: Whether to stream the response
            
        Returns:
            ChatCompletion object
            
        Raises:
            OpenAIError: If request fails after retries
        """
        # Validate messages
        if not messages:
            raise ValueError("At least one message is required")
        
        for msg in messages:
            if "role" not in msg or "content" not in msg:
                raise ValueError("Each message must have 'role' and 'content' fields")
            if msg["role"] not in ["system", "user", "assistant"]:
                raise ValueError(f"Invalid role: {msg['role']}")
        
        # Estimate tokens (rough estimate)
        total_text = " ".join(msg.get("content", "") for msg in messages)
        estimated_tokens = self._estimate_tokens(total_text)
        if max_tokens:
            estimated_tokens += max_tokens
        
        # Check rate limits
        await self._check_rate_limit(model, estimated_tokens=estimated_tokens)
        
        # Create completion with retry
        async def _create_completion():
            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=stream
                )
                return response
            except Exception as e:
                raise self._parse_error(e)
        
        try:
            completion = await self._retry_with_backoff(_create_completion)
            
            # Record request (use actual tokens if available)
            tokens_used = 0
            if hasattr(completion, 'usage') and completion.usage:
                tokens_used = completion.usage.total_tokens
            else:
                tokens_used = estimated_tokens
            
            await self._record_request(model, tokens_used)
            
            logger.info(f"Chat completion created successfully (tokens: {tokens_used})")
            return completion
            
        except OpenAIError as e:
            logger.error(f"Failed to create chat completion: {e.message}")
            raise
    
    async def create_chat_completion_simple(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Simplified chat completion that returns just the text response.
        
        Args:
            prompt: User prompt
            system_message: Optional system message
            model: Chat model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            
        Returns:
            Response text content
            
        Raises:
            OpenAIError: If request fails
        """
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})
        
        completion = await self.create_chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return completion.choices[0].message.content
    
    def is_configured(self) -> bool:
        """Check if OpenAI service is properly configured"""
        return bool(self.api_key)

