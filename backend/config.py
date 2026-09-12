from typing import Optional, Union
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram configuration
    TELEGRAM_BOT_TOKEN: str = "placeholder_token"
    TELEGRAM_SUPPORT_GROUP_ID: Union[int, str] = 0

    # Backend configuration
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    BACKEND_URL: str = "http://localhost:8000"
    DATABASE_URL: str = "sqlite+aiosqlite:///./chatbot.db"

    # AI & Knowledge Base configuration
    AI_ENABLED: bool = False
    AI_API_KEY: Optional[str] = None
    AI_MODEL: str = "gpt-4o-mini"
    AI_PROVIDER: str = "openai"
    KB_CONFIDENCE_THRESHOLD: float = 0.3

    # Email & SMTP configuration
    EMAIL_ENABLED: bool = False
    SMTP_HOST: str = "smtp.example.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: str = "support-bot@example.com"
    SUPPORT_EMAIL_RECIPIENT: str = "support-team@example.com"
    SMTP_USE_TLS: bool = True


settings = Settings()
