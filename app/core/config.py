"""
Application configuration settings
"""

from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "Clause Haus"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000  # Default port, Railway sets PORT env var which Pydantic will read
    
    # Masumi Payment Service Configuration
    PAYMENT_SERVICE_URL: Optional[str] = None
    PAYMENT_API_KEY: Optional[str] = None
    SELLER_VKEY: Optional[str] = None
    NETWORK: str = "Preprod"  # "Preprod" or "Mainnet"
    AGENT_IDENTIFIER: Optional[str] = None  # Obtained after agent registration
    PAYMENT_AMOUNT: Optional[int] = None  # Payment amount (e.g., 10000000 for 10 ADA in lovelace)
    PAYMENT_UNIT: str = "lovelace"  # Payment unit (default: lovelace)
    
    # CORS
    CORS_ORIGINS: List[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    
    # Database (for future use)
    DATABASE_URL: Optional[str] = None
    
    # BGB Parser API Key
    API_KEY: Optional[str] = None
    
    # OpenAI Configuration
    OPENAI_API_KEY: Optional[str] = None
    
    # Mistral Configuration
    MISTRAL_API_KEY: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

