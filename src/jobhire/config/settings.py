"""
Enterprise application settings with comprehensive configuration management.
"""

import os
from functools import lru_cache
from typing import List, Optional, Set
from pydantic import Field, validator
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""

    # MongoDB (Primary)
    mongodb_url: str = Field(default="mongodb://localhost:27017", env="MONGODB_URL")
    mongodb_database: str = Field(default="jobhire_ai", env="MONGODB_DATABASE")
    mongodb_test_database: str = Field(default="jobhire_ai_test", env="MONGODB_TEST_DATABASE")
    mongodb_min_pool_size: int = Field(default=10, env="MONGODB_MIN_POOL_SIZE")
    mongodb_max_pool_size: int = Field(default=100, env="MONGODB_MAX_POOL_SIZE")

    # Redis (Cache & Queue)
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    redis_max_connections: int = Field(default=100, env="REDIS_MAX_CONNECTIONS")
    redis_socket_keepalive: bool = Field(default=True, env="REDIS_SOCKET_KEEPALIVE")
    redis_retry_on_timeout: bool = Field(default=True, env="REDIS_RETRY_ON_TIMEOUT")


class SecuritySettings(BaseSettings):
    """Security configuration settings."""

    # JWT Configuration
    secret_key: str = Field(default="dev-secret-key-change-in-production", env="SECRET_KEY")
    algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, env="REFRESH_TOKEN_EXPIRE_DAYS")

    # Password Security
    password_min_length: int = Field(default=8, env="PASSWORD_MIN_LENGTH")
    password_require_uppercase: bool = Field(default=True, env="PASSWORD_REQUIRE_UPPERCASE")
    password_require_lowercase: bool = Field(default=True, env="PASSWORD_REQUIRE_LOWERCASE")
    password_require_numbers: bool = Field(default=True, env="PASSWORD_REQUIRE_NUMBERS")
    password_require_special: bool = Field(default=True, env="PASSWORD_REQUIRE_SPECIAL")

    # API Security
    api_keys: Optional[str] = Field(default=None, env="API_KEYS")
    rate_limit_requests_per_minute: int = Field(default=100, env="RATE_LIMIT_REQUESTS_PER_MINUTE")
    rate_limit_burst: int = Field(default=20, env="RATE_LIMIT_BURST")

    # CORS
    allowed_origins: List[str] = Field(default=["http://localhost:3000"], env="ALLOWED_ORIGINS")
    allowed_methods: List[str] = Field(default=["GET", "POST", "PUT", "DELETE", "PATCH"], env="ALLOWED_METHODS")
    allowed_headers: List[str] = Field(default=["*"], env="ALLOWED_HEADERS")

    @validator("allowed_origins", pre=True)
    def parse_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def api_keys_list(self) -> List[str]:
        """Get API keys as a list."""
        if not self.api_keys:
            return []
        return [key.strip() for key in self.api_keys.split(",")]


class MonitoringSettings(BaseSettings):
    """Monitoring and observability settings."""

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")  # json or console
    log_file_path: Optional[str] = Field(default=None, env="LOG_FILE_PATH")

    # Metrics
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    metrics_port: int = Field(default=8001, env="METRICS_PORT")
    prometheus_endpoint: str = Field(default="/metrics", env="PROMETHEUS_ENDPOINT")

    # Tracing
    enable_tracing: bool = Field(default=False, env="ENABLE_TRACING")
    jaeger_endpoint: Optional[str] = Field(default=None, env="JAEGER_ENDPOINT")
    trace_sampling_rate: float = Field(default=0.1, env="TRACE_SAMPLING_RATE")

    # Error Tracking
    sentry_dsn: Optional[str] = Field(default=None, env="SENTRY_DSN")
    sentry_environment: str = Field(default="development", env="SENTRY_ENVIRONMENT")
    sentry_traces_sample_rate: float = Field(default=0.1, env="SENTRY_TRACES_SAMPLE_RATE")


class AISettings(BaseSettings):
    """AI and ML service configuration."""

    # OpenAI
    openai_api_key: str = Field(default="sk-dev-key-change-in-production", env="OPENAI_API_KEY")
    openai_organization: Optional[str] = Field(default=None, env="OPENAI_ORGANIZATION")
    openai_default_model: str = Field(default="gpt-4", env="OPENAI_DEFAULT_MODEL")
    openai_cheap_model: str = Field(default="gpt-3.5-turbo", env="OPENAI_CHEAP_MODEL")
    openai_max_tokens: int = Field(default=4000, env="OPENAI_MAX_TOKENS")
    openai_temperature: float = Field(default=0.7, env="OPENAI_TEMPERATURE")

    # Replicate
    replicate_api_token: str = Field(default="dev-replicate-token", env="REPLICATE_API_TOKEN")

    # AI Processing Limits
    max_concurrent_ai_requests: int = Field(default=10, env="MAX_CONCURRENT_AI_REQUESTS")
    ai_request_timeout: int = Field(default=60, env="AI_REQUEST_TIMEOUT")
    ai_retry_attempts: int = Field(default=3, env="AI_RETRY_ATTEMPTS")


class ExternalServicesSettings(BaseSettings):
    """External service configuration."""

    # Job Search APIs
    jsearch_api_key: str = Field(default="dev-jsearch-key", env="JSEARCH_API_KEY")
    jsearch_api_host: str = Field(default="jsearch.p.rapidapi.com", env="JSEARCH_API_HOST")
    rapid_api_key: str = Field(default="dev-rapid-api-key", env="RAPID_API_KEY")

    # LinkedIn Automation
    linkedin_email: Optional[str] = Field(default=None, env="LINKEDIN_EMAIL")
    linkedin_password: Optional[str] = Field(default=None, env="LINKEDIN_PASSWORD")
    linkedin_headless: bool = Field(default=True, env="LINKEDIN_HEADLESS")
    linkedin_apply_limit: int = Field(default=50, env="LINKEDIN_APPLY_LIMIT")

    # Email Service
    smtp_server: str = Field(default="smtp.gmail.com", env="SMTP_SERVER")
    smtp_port: int = Field(default=587, env="SMTP_PORT")
    smtp_username: Optional[str] = Field(default=None, env="SMTP_USERNAME")
    smtp_password: Optional[str] = Field(default=None, env="SMTP_PASSWORD")
    email_from: str = Field(default="noreply@jobhire.ai", env="EMAIL_FROM")

    # Payment Processing
    stripe_publishable_key: Optional[str] = Field(default=None, env="STRIPE_PUBLISHABLE_KEY")
    stripe_secret_key: Optional[str] = Field(default=None, env="STRIPE_SECRET_KEY")
    stripe_webhook_secret: Optional[str] = Field(default=None, env="STRIPE_WEBHOOK_SECRET")


class PerformanceSettings(BaseSettings):
    """Performance and optimization settings."""

    # Caching
    cache_ttl_default: int = Field(default=300, env="CACHE_TTL_DEFAULT")  # 5 minutes
    cache_ttl_user_profile: int = Field(default=1800, env="CACHE_TTL_USER_PROFILE")  # 30 minutes
    cache_ttl_job_data: int = Field(default=3600, env="CACHE_TTL_JOB_DATA")  # 1 hour

    # Request Limits
    max_jobs_per_search: int = Field(default=100, env="MAX_JOBS_PER_SEARCH")
    max_applications_per_day: int = Field(default=50, env="MAX_APPLICATIONS_PER_DAY")
    max_file_size_mb: int = Field(default=10, env="MAX_FILE_SIZE_MB")

    # Background Tasks
    celery_broker_url: str = Field(default="redis://localhost:6379/0", env="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/0", env="CELERY_RESULT_BACKEND")
    celery_task_serializer: str = Field(default="json", env="CELERY_TASK_SERIALIZER")
    celery_result_serializer: str = Field(default="json", env="CELERY_RESULT_SERIALIZER")
    celery_timezone: str = Field(default="UTC", env="CELERY_TIMEZONE")

    # Worker Configuration
    worker_concurrency: int = Field(default=4, env="WORKER_CONCURRENCY")
    worker_prefetch_multiplier: int = Field(default=1, env="WORKER_PREFETCH_MULTIPLIER")


class Settings(BaseSettings):
    """Main application settings combining all configuration sections."""

    # Application
    app_name: str = Field(default="JobHire.AI Enterprise", env="APP_NAME")
    app_version: str = Field(default="2.0.0", env="APP_VERSION")
    app_environment: str = Field(default="development", env="APP_ENVIRONMENT")
    app_host: str = Field(default="0.0.0.0", env="APP_HOST")
    app_port: int = Field(default=8000, env="APP_PORT")
    app_debug: bool = Field(default=False, env="APP_DEBUG")

    # Frontend
    frontend_url: str = Field(default="http://localhost:3000", env="FRONTEND_URL")

    # Configuration sections
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    ai: AISettings = Field(default_factory=AISettings)
    external: ExternalServicesSettings = Field(default_factory=ExternalServicesSettings)
    performance: PerformanceSettings = Field(default_factory=PerformanceSettings)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"

    @validator("app_environment")
    def validate_environment(cls, v):
        valid_environments = {"development", "staging", "production", "testing"}
        if v not in valid_environments:
            raise ValueError(f"Environment must be one of {valid_environments}")
        return v

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app_environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app_environment == "production"

    @property
    def is_testing(self) -> bool:
        """Check if running in testing mode."""
        return self.app_environment == "testing"


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()