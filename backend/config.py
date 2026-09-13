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
    # Which LLM provider to use: "openai", "gemini", or "deepseek".
    AI_PROVIDER: str = "openai"
    # Model name for the selected provider. Leave unset to use a sane default
    # per provider (see AIAssistantService.DEFAULT_MODELS).
    AI_MODEL: Optional[str] = None
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

    # Inbound email webhook security
    # Shared secret used to verify the HMAC-SHA256 signature of inbound webhook
    # requests (header: X-Webhook-Signature). Must be set to a strong random
    # value in production, and shared with whatever forwards emails to this
    # endpoint (e.g. the email provider or an IMAP relay script).
    EMAIL_WEBHOOK_SECRET: Optional[str] = None

    # Brevo Inbound Parsing webhook security
    # Shared secret Brevo is configured to send back as a `?token=` query
    # parameter on every call to /api/webhooks/email-inbound/brevo (Brevo does
    # not sign its webhook requests or support a custom header, so a secret
    # embedded in the URL is the only practical authentication). Must be set
    # to a strong random value in production. Kept distinct from
    # EMAIL_WEBHOOK_SECRET since the two protect different transports (a URL
    # token vs. a body HMAC) with different exposure risks.
    BREVO_INBOUND_SECRET: Optional[str] = None

    # Backend API authentication
    # Shared secret the Telegram bot (and any other trusted caller) must send
    # in the X-API-Key header on every request to the backend API (except
    # /health and /api/webhooks/email-inbound, which has its own HMAC check).
    # Must be set to a strong random value whenever the backend is reachable
    # over a network you don't fully control (e.g. hosted on a public VPS).
    API_KEY: Optional[str] = None

    # CORS: comma-separated list of allowed origins for browser calls to this
    # API (e.g. "https://admin.example.com,https://app.example.com"). Default
    # "*" is fine for local testing/dev, since this API is authenticated via
    # the X-API-Key header (not cookies), so no credentialed CORS request is
    # ever needed. Restrict this to your real origin(s) once you have a web
    # frontend, and keep it as "*" (or empty) if nothing ever calls this API
    # from a browser.
    CORS_ALLOWED_ORIGINS: str = "*"


settings = Settings()
