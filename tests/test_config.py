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
