from typing import Any, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Database
    DATABASE_URL: str = "postgresql://claimguard:secure_password@db:5432/claimguard"
    POSTGRES_USER: str = "claimguard"
    POSTGRES_PASSWORD: str = "secure_password"
    POSTGRES_DB: str = "claimguard"

    # Application
    APP_ENV: str = "development"
    APP_NAME: str = "ClaimGuard AI"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production-min-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ENCRYPTION_KEY: str = "your-encryption-key-change-in-production-32-chars"

    # AI/ML
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "llama3.2"
    OLLAMA_TIMEOUT: int = 30

    # Frontend
    FRONTEND_URL: str = "http://localhost:5173"


settings = Settings()
