# config/settings.py
"""
Application settings using Pydantic BaseSettings
Handles environment variables and configuration
"""

from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional
from pydantic import Field

class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=False,
        protected_namespaces=('settings_',)
    )
    
    # Environment
    environment: str = "development"
    
    # Database Configuration
    redis_url: str = "redis://localhost:6379/0"
    postgres_url: Optional[str] = None
    pinecone_api_key: Optional[str] = None
    pinecone_environment: str = "us-east1-gcp"
    
    # LLM Configuration
    openai_api_key: Optional[str] = None
    llm_model_name: str = "llama-3.3-70b-versatile"  # Renamed from model_name to avoid Pydantic conflict
    max_tokens: int = 1000
    temperature: float = 0.7
    
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
    default_rate_limit_per_day: int = 10000
    
    # Message Bus Settings
    max_message_size: int = 10000  # characters
    supported_channels: list = ["whatsapp", "web", "facebook", "telegram", "instagram", "sms", "console"]
    
    # Service URLs (for inter-service communication)
    message_bus_url: str = "http://localhost:8000"
    orchestrator_url: str = "http://localhost:8001"
    intent_agent_url: str = "http://localhost:8002"
    rag_agent_url: str = "http://localhost:8003"
    cart_agent_url: str = "http://localhost:8004"
    sales_agent_url: str = "http://localhost:8005"
    
    # Health Check Settings
    health_check_timeout: int = 5
    health_check_interval: int = 30
    
    # Performance Settings
    max_concurrent_requests: int = 100
    request_timeout: int = 30
    
    # Development Settings
    debug_mode: bool = False
    reload_on_change: bool = False

    groq_api_key: str = Field(default="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", env="groq_api_key")
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1", env="groq_base_url")
    groq_model_name: str = Field(default="llama-3.3-70b-versatile", env="groq_model_name")
    groq_max_tokens: int = Field(default=400000, env="groq_max_tokens")
    groq_temperature: float = Field(default=0.1, env="groq_temperature")
settings = Settings()