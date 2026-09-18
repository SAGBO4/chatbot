import os
import pytest
from backend.config import Settings


def test_settings_defaults():
    # _env_file=None bypasses the project's real .env, so this checks pure
    # class defaults regardless of what a developer has configured locally.
    s = Settings(
        _env_file=None,
        TELEGRAM_BOT_TOKEN="test_token",
        TELEGRAM_SUPPORT_GROUP_ID=-100123456,
    )
    assert s.TELEGRAM_BOT_TOKEN == "test_token"
    assert s.TELEGRAM_SUPPORT_GROUP_ID == -100123456
    assert s.AI_ENABLED is False
    assert s.KB_CONFIDENCE_THRESHOLD == 0.3
    assert "sqlite" in s.DATABASE_URL


def test_settings_environment_override(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env_token_xyz")
    monkeypatch.setenv("TELEGRAM_SUPPORT_GROUP_ID", "-100999999")
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("KB_CONFIDENCE_THRESHOLD", "0.75")
    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.setenv("SUPPORT_EMAIL_RECIPIENT", "team@example.com")

    s = Settings()
    assert s.TELEGRAM_BOT_TOKEN == "env_token_xyz"
    assert s.TELEGRAM_SUPPORT_GROUP_ID == "-100999999" or s.TELEGRAM_SUPPORT_GROUP_ID == -100999999
    assert s.AI_ENABLED is True
    assert s.KB_CONFIDENCE_THRESHOLD == 0.75
    assert s.EMAIL_ENABLED is True
    assert s.SUPPORT_EMAIL_RECIPIENT == "team@example.com"


def test_support_group_is_configured():
    unconfigured_default = Settings(_env_file=None, TELEGRAM_BOT_TOKEN="t")
    assert unconfigured_default.support_group_is_configured() is False

    unconfigured_zero = Settings(_env_file=None, TELEGRAM_BOT_TOKEN="t", TELEGRAM_SUPPORT_GROUP_ID="0")
    assert unconfigured_zero.support_group_is_configured() is False

    configured = Settings(_env_file=None, TELEGRAM_BOT_TOKEN="t", TELEGRAM_SUPPORT_GROUP_ID=-100123456)
    assert configured.support_group_is_configured() is True


def test_community_group_is_configured():
    unconfigured_default = Settings(_env_file=None, TELEGRAM_BOT_TOKEN="t")
    assert unconfigured_default.community_group_is_configured() is False

    unconfigured_zero = Settings(_env_file=None, TELEGRAM_BOT_TOKEN="t", TELEGRAM_COMMUNITY_GROUP_ID="0")
    assert unconfigured_zero.community_group_is_configured() is False

    configured = Settings(_env_file=None, TELEGRAM_BOT_TOKEN="t", TELEGRAM_COMMUNITY_GROUP_ID=-100987654)
    assert configured.community_group_is_configured() is True


def test_community_feature_defaults():
    s = Settings(_env_file=None, TELEGRAM_BOT_TOKEN="t")
    assert s.COMMUNITY_RESOLUTION_TIMEOUT_SECONDS == 600
    assert s.CRYPTO_PROVIDER_TIMEOUT_SECONDS == 10.0
    assert s.CRYPTO_CACHE_TTL_SECONDS == 45


def test_is_bot_owner_unset_grants_no_one():
    s = Settings(_env_file=None, TELEGRAM_BOT_TOKEN="t")
    assert s.BOT_OWNER_TELEGRAM_ID is None
    assert s.is_bot_owner(12345) is False


def test_is_bot_owner_matches_configured_id():
    s = Settings(_env_file=None, TELEGRAM_BOT_TOKEN="t", BOT_OWNER_TELEGRAM_ID=999)
    assert s.is_bot_owner(999) is True
    assert s.is_bot_owner(1000) is False


def test_blank_bot_owner_id_env_var_does_not_crash(monkeypatch):
    # Regression: an empty BOT_OWNER_TELEGRAM_ID= line (the .env.example
    # template's default before an operator fills it in) used to raise a
    # pydantic ValidationError at Settings() construction time.
    monkeypatch.setenv("BOT_OWNER_TELEGRAM_ID", "")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    s = Settings(_env_file=None)
    assert s.BOT_OWNER_TELEGRAM_ID is None
    assert s.is_bot_owner(1) is False


def test_is_email_configured():
    # Disabled by default
    s_default = Settings(_env_file=None, TELEGRAM_BOT_TOKEN="t")
    assert s_default.is_email_configured() is False

    # Enabled but with placeholder host
    s_placeholder = Settings(
        _env_file=None,
        TELEGRAM_BOT_TOKEN="t",
        EMAIL_ENABLED=True,
        SMTP_HOST="smtp.example.com",
        SUPPORT_EMAIL_RECIPIENT="real@stackwallet.com",
    )
    assert s_placeholder.is_email_configured() is False

    # Enabled but with placeholder recipient
    s_placeholder_recip = Settings(
        _env_file=None,
        TELEGRAM_BOT_TOKEN="t",
        EMAIL_ENABLED=True,
        SMTP_HOST="smtp.mailgun.org",
        SUPPORT_EMAIL_RECIPIENT="support-team@example.com",
    )
    assert s_placeholder_recip.is_email_configured() is False

    # Fully configured
    s_valid = Settings(
        _env_file=None,
        TELEGRAM_BOT_TOKEN="t",
        EMAIL_ENABLED=True,
        SMTP_HOST="smtp.brevo.com",
        SUPPORT_EMAIL_RECIPIENT="support@stackwallet.com",
    )
    assert s_valid.is_email_configured() is True


def test_is_email_inbound_configured():
    # Disabled
    s_default = Settings(_env_file=None, TELEGRAM_BOT_TOKEN="t")
    assert s_default.is_email_inbound_configured() is False

    # Enabled without secret
    s_no_secret = Settings(_env_file=None, TELEGRAM_BOT_TOKEN="t", EMAIL_ENABLED=True)
    assert s_no_secret.is_email_inbound_configured() is False

    # Enabled with EMAIL_WEBHOOK_SECRET
    s_generic = Settings(_env_file=None, TELEGRAM_BOT_TOKEN="t", EMAIL_ENABLED=True, EMAIL_WEBHOOK_SECRET="secret")
    assert s_generic.is_email_inbound_configured() is True

    # Enabled with BREVO_INBOUND_SECRET
    s_brevo = Settings(_env_file=None, TELEGRAM_BOT_TOKEN="t", EMAIL_ENABLED=True, BREVO_INBOUND_SECRET="secret")
    assert s_brevo.is_email_inbound_configured() is True

