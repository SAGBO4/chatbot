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
    BACKEND_HOST: str = "0.0.0.0"  # nosec: B104
    BACKEND_PORT: int = 8000
    BACKEND_URL: str = "http://localhost:8000"
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/chatbot.db"

    # Monitoring & Telemetry
    SENTRY_DSN: Optional[str] = None

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

    # Comma-separated list of email addresses or domains (@domain.com) authorized to resolve
    # tickets via inbound email webhooks. If empty, all senders presenting valid webhook secrets are accepted.
    ALLOWED_SUPPORT_EMAIL_SENDERS: str = ""

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

    def support_group_is_configured(self) -> bool:
        """
        Whether TELEGRAM_SUPPORT_GROUP_ID points to a real Telegram group.

        The default `0` (and any falsy value) means "not configured yet".
        Single source of truth for this check - it used to be copy-pasted as
        `not group_id or str(group_id) == "0"` in three places (bot support
        handlers, bot user handlers, backend telegram relay), which risked
        drifting out of sync.
        """
        return bool(self.TELEGRAM_SUPPORT_GROUP_ID) and str(self.TELEGRAM_SUPPORT_GROUP_ID) != "0"

    def is_authorized_email_sender(self, sender: str) -> bool:
        """
        Validates if an inbound email sender is authorized to resolve tickets.
        If ALLOWED_SUPPORT_EMAIL_SENDERS is set, checks against the comma-separated
        list of allowed emails or domains (e.g. '@stackwallet.com, support@stackwallet.com').
        If empty, all senders with valid webhook secrets are accepted.
        """
        if not self.ALLOWED_SUPPORT_EMAIL_SENDERS:
            return True
        allowed = [s.strip().lower() for s in self.ALLOWED_SUPPORT_EMAIL_SENDERS.split(",") if s.strip()]
        sender_lower = sender.strip().lower()
        for item in allowed:
            if item.startswith("@") and sender_lower.endswith(item):
                return True
            if sender_lower == item:
                return True
        return False


settings = Settings()
