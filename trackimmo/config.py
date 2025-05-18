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
    
    # Database
    DATABASE_URL: Optional[str] = "sqlite:///./test.db"  # Default for development
    
    # Supabase configuration
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    
    # API configuration
    API_KEY: str = ""
    API_BASE_URL: str = ""

    # Email configuration
    EMAIL_SENDER: str = ""
    SMTP_SERVER: str = "smtp.hostinger.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    CTO_EMAIL: str = ""

    # CORS
    CORS_ORIGINS: List[str] = ["*"]
    
    # Scraping
    SCRAPER_HEADLESS: bool = True
    SCRAPER_TIMEOUT: int = 30
    SCRAPER_USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    SCRAPER_MAX_RETRIES: int = 3
    SCRAPER_DELAY: float = 1.0  # in seconds
    
    # Geocoding
    GEOCODING_API_URL: str = "https://api-adresse.data.gouv.fr/search/csv/"
    GEOCODING_BATCH_SIZE: int = 1000
    
    # DPE API
    DPE_EXISTING_BUILDINGS_API: str = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-v2-logements-existants/lines"
    DPE_NEW_BUILDINGS_API: str = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe-v2-logements-neufs/lines"
    DPE_MAX_RETRIES: int = 3
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # Metrics
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 8001
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True)
    
    @field_validator("DATABASE_URL")
    def validate_database_url(cls, v: Optional[str]) -> str:
        """Validate the database URL."""
        return v


# Create global settings instance
settings = Settings() 