"""
OpenAI-related Pydantic schemas and types
"""

from typing import List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from openai.types import Embedding


class OpenAIErrorType(str, Enum):
    """Types of OpenAI API errors"""
    RATE_LIMIT = "rate_limit"
    TOKEN_LIMIT = "token_limit"
    INVALID_REQUEST = "invalid_request"
    AUTHENTICATION = "authentication"
    PERMISSION = "permission"
    SERVER_ERROR = "server_error"
    NETWORK = "network"
    UNKNOWN = "unknown"


class OpenAIError(Exception):
    """Custom OpenAI service error"""
    def __init__(self, message: str, error_type: OpenAIErrorType, retry_after: Optional[float] = None):
        self.message = message
        self.error_type = error_type
        self.retry_after = retry_after
        super().__init__(self.message)


class EmbeddingRequest(BaseModel):
    """Request for embedding generation"""
    text: str = Field(..., min_length=1, description="Text to embed")
    model: Optional[str] = Field(default=None, description="Embedding model to use (optional)")


class ChatMessage(BaseModel):
    """Chat message for completion"""
    role: str = Field(..., pattern="^(system|user|assistant)$")
    content: str = Field(..., min_length=1)

    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        allowed = {"system", "user", "assistant"}
        if v not in allowed:
            raise ValueError(f"Role must be one of {allowed}")
        return v



