"""
OpenAI-related Pydantic schemas and types
"""

from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from openai.types import Embedding, ChatCompletion


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
    model: str = Field(default="text-embedding-3-small", description="Embedding model to use")


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


class ChatRequest(BaseModel):
    """Request for chat completion"""
    messages: List[ChatMessage] = Field(..., min_length=1)
    model: str = Field(default="gpt-4o-mini", description="Chat model to use")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=4096)
    stream: bool = Field(default=False)


class EmbeddingResponse(BaseModel):
    """Response for embedding generation"""
    embeddings: List[Embedding] = Field(..., description="List of embedding objects")
    model: str = Field(..., description="Model used for embeddings")
    total_texts: int = Field(..., description="Total number of texts embedded")


class ChatResponse(BaseModel):
    """Response for chat completion"""
    completion: ChatCompletion = Field(..., description="Chat completion object")
    content: str = Field(..., description="Extracted message content")
    tokens_used: int = Field(..., description="Total tokens used in request and response")

