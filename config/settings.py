# config/settings.py
"""
Application settings using Pydantic BaseSettings
Handles environment variables and configuration
"""

from pydantic import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Environment
    environment: str = "development"
    
    # Database Configuration
    redis_url: str = "redis://localhost:6379/0"
    postgres_url: Optional[str] = None
    pinecone_api_key: Optional[str] = None
    pinecone_environment: str = "us-east1-gcp"
    
    # LLM Configuration
    openai_api_key: Optional[str] = None
    model_name: str = "gpt-4"
    max_tokens: int = 1000
    
    # Channel API Keys
    whatsapp_token: Optional[str] = None
    whatsapp_verify_token: Optional[str] = None
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    facebook_app_secret: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    
    # Security
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    # Caching
    cache_ttl_seconds: int = 3600
    semantic_cache_enabled: bool = True
    
    # Observability
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    log_level: str = "INFO"
    
    # Rate Limiting Defaults
    default_rate_limit_per_minute: int = 60
    default_rate_limit_per_hour: int = 1000
    
    # Message Bus Settings
    max_message_size: int = 10000  # characters
    supported_channels: list = ["whatsapp", "web", "facebook", "telegram", "instagram", "sms", "console"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()