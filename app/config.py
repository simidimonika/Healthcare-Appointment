import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "ClinicPulse AI - Healthcare Manager"
    APP_ENV: str = "development"
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    DEBUG: bool = True

    # Security
    SECRET_KEY: str = "insecure-secret-key-for-dev-change-in-prod-32-chars-long"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Database
    DATABASE_URL: str = "sqlite:///./healthcare.db"

    # LLM Settings
    LLM_PROVIDER: str = "gemini"  # 'gemini', 'openai', or 'mock'
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gemini-1.5-flash"

    # Email Settings
    EMAIL_BACKEND: str = "mock"  # 'smtp', 'console', or 'mock'
    SMTP_HOST: str = "smtp.sendgrid.net"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = "apikey"
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "no-reply@clinicpulse.health"
    SMTP_FROM_NAME: str = "ClinicPulse AI Health"

    # Google Calendar
    GOOGLE_CALENDAR_ENABLED: bool = True
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/calendar/oauth2callback"

    # Concurrency & Background Worker
    SLOT_HOLD_TTL_MINUTES: int = 5
    MEDICATION_REMINDER_CHECK_INTERVAL_SECONDS: int = 60
    NOTIFICATION_RETRY_INTERVAL_SECONDS: int = 120
    MAX_NOTIFICATION_RETRIES: int = 3

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
