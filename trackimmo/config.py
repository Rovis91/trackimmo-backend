"""
Configuration module for TrackImmo backend.

This module loads configuration variables from environment variables.
"""
import os
from typing import Optional, List, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    """Configuration settings for the application."""
    
    # API configurations
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "TrackImmo API"
    DEBUG: bool = False
    
    # Security
    SECRET_KEY: str = "dev_secret_key"  # Default for development
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    ALGORITHM: str = "HS256"
    
    # API Keys
    API_KEY: str = ""
    ADMIN_API_KEY: str = ""  # Separate admin key for sensitive operations
    
    # Database
    DATABASE_URL: Optional[str] = None  # Should be set via environment variable
    
    # Supabase configuration
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    
    # API configuration
    API_BASE_URL: str = ""  # Load from .env

    # Email configuration
    EMAIL_SENDER: str = ""  # Load from .env
    SMTP_SERVER: str = ""  # Load from .env
    SMTP_PORT: int = 465  # Default port, can be overridden in .env
    SMTP_USERNAME: str = ""  # Load from .env
    SMTP_PASSWORD: str = ""  # Load from .env
    CTO_EMAIL: str = ""  # Load from .env
    
    # Email settings
    EMAIL_MAX_RETRIES: int = 3
    EMAIL_RETRY_DELAY: int = 2  # seconds
    EMAIL_RATE_LIMIT: int = 100  # emails per hour

    # CORS
    CORS_ORIGINS: List[str] = ["*"]
    
    # Scraping configuration
    SCRAPER_HEADLESS: bool = True
    SCRAPER_TIMEOUT: int = 30
    SCRAPER_USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    SCRAPER_MAX_RETRIES: int = 3
    SCRAPER_DELAY: float = 0.2  # in seconds
    SCRAPER_BROWSER_POOL_SIZE: int = 30
    SCRAPER_BROWSER_TIMEOUT: int = 60
    
    # Scraping date range configuration
    SCRAPER_DEFAULT_START_DATE: str = "01/2014"  # Format: MM/YYYY
    SCRAPER_DEFAULT_END_DATE: str = "12/2024"    # Format: MM/YYYY
    
    # Client processing settings
    DEFAULT_ADDRESSES_PER_REPORT: int = 10
    MIN_PROPERTY_AGE_YEARS: int = 6
    MAX_PROPERTY_AGE_YEARS: int = 8
    MIN_PROPERTIES_PER_CITY: int = 50  # Minimum before scraping more
    
    # Job processing settings
    MAX_JOB_RETRIES: int = 3
    JOB_RETRY_DELAY_HOURS: int = 1
    JOB_CLEANUP_DAYS: int = 7  # Days to keep completed jobs
    
    # Geocoding
    GEOCODING_API_URL: str = "https://api-adresse.data.gouv.fr/search/csv/"
    GEOCODING_BATCH_SIZE: int = 1000
    
    # DPE API
    DPE_EXISTING_BUILDINGS_API: str = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-v2-logements-existants/lines"
    DPE_NEW_BUILDINGS_API: str = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-v2-logements-neufs/lines"
    DPE_MAX_RETRIES: int = 3
    DPE_CACHE_DURATION_DAYS: int = 30
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE_MAX_SIZE: int = 10  # MB (deprecated - using TimedRotatingFileHandler now)
    LOG_FILE_BACKUP_COUNT: int = 30  # Days of log retention
    
    # Metrics
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 8001
    
    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 3600  # seconds (1 hour)
    
    # Background tasks
    MAX_BACKGROUND_TASKS: int = 10
    BACKGROUND_TASK_TIMEOUT: int = 3600  # seconds (1 hour)
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True)
    
    @field_validator("DATABASE_URL")
    def validate_database_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate the database URL."""
        return v  # Let it be None if not provided, Supabase will be used instead
    
    @field_validator("ADMIN_API_KEY", mode="before")
    def set_admin_api_key(cls, v, values):
        """Set admin API key to main API key if not provided."""
        if not v and 'API_KEY' in values.data:
            return values.data['API_KEY']
        return v
    
    @field_validator("CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    def get_property_age_range_days(self) -> tuple[int, int]:
        """Get property age range in days."""
        min_days = self.MIN_PROPERTY_AGE_YEARS * 365
        max_days = self.MAX_PROPERTY_AGE_YEARS * 365
        return min_days, max_days
    
    def is_production(self) -> bool:
        """Check if running in production."""
        return not self.DEBUG and "localhost" not in self.API_BASE_URL.lower()


# Create global settings instance
settings = Settings()

# Validate critical settings on import
def validate_critical_settings():
    """Validate critical settings and warn about missing values."""
    import logging
    logger = logging.getLogger(__name__)
    
    critical_settings = {
        'SUPABASE_URL': settings.SUPABASE_URL,
        'SUPABASE_KEY': settings.SUPABASE_KEY,
        'API_KEY': settings.API_KEY,
    }
    
    missing_critical = [name for name, value in critical_settings.items() if not value]
    
    if missing_critical:
        logger.warning(f"Missing critical settings: {', '.join(missing_critical)}")
        if settings.is_production():
            raise ValueError(f"Critical settings missing in production: {', '.join(missing_critical)}")
    
    # Warn about email settings
    email_settings = {
        'EMAIL_SENDER': settings.EMAIL_SENDER,
        'SMTP_USERNAME': settings.SMTP_USERNAME,
        'SMTP_PASSWORD': settings.SMTP_PASSWORD,
    }
    
    missing_email = [name for name, value in email_settings.items() if not value]
    
    if missing_email:
        logger.warning(f"Email settings missing: {', '.join(missing_email)}. Email functionality will be disabled.")

# Run validation on import
try:
    validate_critical_settings()
except Exception as e:
    print(f"Configuration validation warning: {e}")