"""
Configuration settings for JobHire.AI Backend
"""

from pydantic_settings import BaseSettings
from typing import List, Optional, Union
import os


class Settings(BaseSettings):
    """Application settings"""

    # App Configuration
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_DEBUG: bool = True

    # MongoDB Database
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DATABASE: str = "jobhire_ai"
    TEST_MONGODB_DATABASE: str = "jobhire_ai_test"

    # Legacy PostgreSQL (for migration period)
    DATABASE_URL: Optional[str] = None
    TEST_DATABASE_URL: Optional[str] = None

    # AI Services
    REPLICATE_API_TOKEN: str
    OPENAI_API_KEY: str

    # Job APIs
    JSEARCH_API_KEY: str
    RAPID_API_KEY: str

    # LinkedIn Automation
    LINKEDIN_EMAIL: Optional[str] = None
    LINKEDIN_PASSWORD: Optional[str] = None
    LINKEDIN_HEADLESS: bool = True
    LINKEDIN_APPLY_LIMIT: int = 50  # Max applications per day

    # Queue System
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # CORS
    FRONTEND_URL: str = "http://localhost:3000"
    ALLOWED_ORIGINS: Union[str, List[str]] = "http://localhost:3000"
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours (for development)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 days
    API_KEYS: Optional[str] = None  # Comma-separated list of valid API keys

    # Stripe Payment
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None

    # Email Forwarding
    EMAIL_FORWARDING_DOMAIN: str = "apply.applyrush.ai"
    AWS_SES_REGION: str = "us-east-1"
    AWS_SES_ACCESS_KEY: Optional[str] = None
    AWS_SES_SECRET_KEY: Optional[str] = None

    # File Storage
    AWS_S3_BUCKET: Optional[str] = None
    AWS_S3_REGION: str = "us-east-1"
    CLOUDFLARE_R2_ACCOUNT_ID: Optional[str] = None
    CLOUDFLARE_R2_ACCESS_KEY: Optional[str] = None
    CLOUDFLARE_R2_SECRET_KEY: Optional[str] = None

    # Rate Limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 100
    RATE_LIMIT_BURST: int = 20
    
    # Monitoring
    ENABLE_METRICS: bool = True
    LOG_LEVEL: str = "INFO"
    
    # AI Model Configuration
    DEFAULT_MODEL: str = "meta/llama-2-70b-chat:02e509c789964a7ea8736978a43525956ef40397be9033abf9fd2badfe68c9e3"
    CHEAP_MODEL: str = "mistralai/mixtral-8x7b-instruct-v0.1"
    PREMIUM_MODEL: str = "anthropic/claude-3-5-sonnet-20241022"
    
    # Job Search Configuration
    MAX_JOBS_PER_SEARCH: int = 100
    JOB_CACHE_TTL: int = 3600  # 1 hour
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if isinstance(self.ALLOWED_ORIGINS, str):
            self.ALLOWED_ORIGINS = [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]


settings = Settings()


def get_settings() -> Settings:
    """Get settings instance (for dependency injection)"""
    return settings