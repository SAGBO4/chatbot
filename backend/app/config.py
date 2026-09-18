from typing import Optional, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from the environment or a `.env` file (see `.env.example`)."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    TELEGRAM_BOT_TOKEN: str = "placeholder_token"
    # Admin/support group. Env-only on purpose: no chat command can redirect ticket traffic.
    TELEGRAM_SUPPORT_GROUP_ID: Union[int, str] = 0
    TELEGRAM_WEBAPP_URL: Optional[str] = None

    # Legacy: only seeds the persisted `community_group_id` setting on first startup
    # (app/services/bot_settings_service.py); afterwards /setup_community is the only way to change it.
    TELEGRAM_COMMUNITY_GROUP_ID: Union[int, str] = 0

    # Always allowed to configure the community group, the admin whitelist and the language.
    # Env-only so this root authority cannot be altered from inside Telegram.
    BOT_OWNER_TELEGRAM_ID: Optional[int] = None

    @field_validator("BOT_OWNER_TELEGRAM_ID", mode="before")
    @classmethod
    def _blank_owner_id_means_unset(cls, value):
        """A blank `BOT_OWNER_TELEGRAM_ID=` (the .env.example default) means "unset"; otherwise `Settings()` fails at import."""
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    # Seconds a community answer's YES/NO buttons stay active
    COMMUNITY_RESOLUTION_TIMEOUT_SECONDS: int = 600

    # Crypto market data (CoinGecko)
    CRYPTO_PROVIDER_TIMEOUT_SECONDS: float = 10.0
    CRYPTO_CACHE_TTL_SECONDS: int = 45

    # Backend
    BACKEND_HOST: str = "0.0.0.0"  # nosec: B104
    BACKEND_PORT: int = 8000
    BACKEND_URL: str = "http://localhost:8000"
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/chatbot.db"

    SENTRY_DSN: Optional[str] = None

    # AI: AI_PROVIDER is "openai", "gemini" or "deepseek"; leave AI_MODEL unset for the
    # provider's default (see AIAssistantService.DEFAULT_MODELS).
    AI_ENABLED: bool = False
    AI_API_KEY: Optional[str] = None
    AI_PROVIDER: str = "openai"
    AI_MODEL: Optional[str] = None
    KB_CONFIDENCE_THRESHOLD: float = 0.3

    # Email & SMTP
    EMAIL_ENABLED: bool = False
    SMTP_HOST: str = "smtp.example.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: str = "support-bot@example.com"
    SUPPORT_EMAIL_RECIPIENT: str = "support-team@example.com"
    SMTP_USE_TLS: bool = True

    # Inbound email webhooks. Two secrets because they protect different transports: a body HMAC
    # (X-Webhook-Signature) and a `?token=` query parameter (Brevo does not sign its requests).
    # Set both to strong random values in production.
    EMAIL_WEBHOOK_SECRET: Optional[str] = None
    BREVO_INBOUND_SECRET: Optional[str] = None

    # Comma-separated addresses or "@domain" suffixes allowed to resolve tickets by email.
    # Empty accepts any sender that presents a valid secret.
    ALLOWED_SUPPORT_EMAIL_SENDERS: str = ""

    # Secret the bot sends as `X-API-Key` on every API request, except /health and the two inbound
    # email webhooks (they check their own secret). Required whenever the backend is reachable
    # over a network you don't control.
    API_KEY: Optional[str] = None

    # Comma-separated browser origins allowed to call the API. "*" is fine for local dev because
    # auth uses `X-API-Key`, not cookies; restrict it once a browser frontend calls the API directly.
    CORS_ALLOWED_ORIGINS: str = "*"

    def support_group_is_configured(self) -> bool:
        """True when TELEGRAM_SUPPORT_GROUP_ID is a real group id; the default 0 (or any falsy value) means "not configured"."""
        return bool(self.TELEGRAM_SUPPORT_GROUP_ID) and str(self.TELEGRAM_SUPPORT_GROUP_ID) != "0"

    def community_group_is_configured(self) -> bool:
        """Same convention as `support_group_is_configured()`; gates the community Q&A, moderation and crypto routers."""
        return bool(self.TELEGRAM_COMMUNITY_GROUP_ID) and str(self.TELEGRAM_COMMUNITY_GROUP_ID) != "0"

    def is_bot_owner(self, user_id: int) -> bool:
        """False when BOT_OWNER_TELEGRAM_ID is unset, so nobody is owner by omission."""
        return self.BOT_OWNER_TELEGRAM_ID is not None and int(user_id) == int(self.BOT_OWNER_TELEGRAM_ID)

    def is_authorized_email_sender(self, sender: str) -> bool:
        """
        Whether an inbound email sender may resolve tickets.

        Any sender when ALLOWED_SUPPORT_EMAIL_SENDERS is empty; otherwise an exact address
        or an "@domain" suffix from that list (e.g. "@stackwallet.com, support@stackwallet.com").
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

    def is_email_configured(self) -> bool:
        """Whether outgoing email is enabled (EMAIL_ENABLED)."""
        return bool(self.EMAIL_ENABLED)

    def is_email_inbound_configured(self) -> bool:
        """Whether inbound email is enabled and at least one webhook secret is set."""
        if not self.EMAIL_ENABLED:
            return False
        return bool(
            (self.EMAIL_WEBHOOK_SECRET and self.EMAIL_WEBHOOK_SECRET.strip())
            or (self.BREVO_INBOUND_SECRET and self.BREVO_INBOUND_SECRET.strip())
        )


settings = Settings()
