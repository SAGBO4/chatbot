import pytest

from app.observability import redact_secrets, scrub

BOT_TOKEN = "123456789:AAH-Secret_Token-Value123"


@pytest.mark.parametrize(
    "text,forbidden",
    [
        (f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", BOT_TOKEN),
        (f"https://api.telegram.org/file/bot{BOT_TOKEN}/photos/file_1.jpg", BOT_TOKEN),
        ("https://x.test/hook?token=abc123&keep=yes", "abc123"),
        ("https://x.test/hook?a=1&api_key=k3y&password=p4ss&secret=s3c", "k3y"),
        ("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&x_cg_demo_api_key=CG-SecretKey12345", "CG-SecretKey12345"),
        ("CoinGecko error 401: Invalid API Key: CG-SecretKey12345", "CG-SecretKey12345"),
        ("Request headers: {'x-cg-demo-api-key': 'CG-SecretKey12345'}", "CG-SecretKey12345"),
    ],
)
def test_redact_secrets_removes_the_secret(text, forbidden):
    assert forbidden not in redact_secrets(text)


def test_redact_secrets_keeps_harmless_parts_readable():
    redacted = redact_secrets(f"POST https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?keep=yes")
    assert redacted == "POST https://api.telegram.org/bot[REDACTED]/sendMessage?keep=yes"


def test_scrub_recurses_into_nested_structures():
    event = {"breadcrumbs": {"values": [{"data": {"url": f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"}}]}, "n": 3}
    cleaned = scrub(event)
    assert BOT_TOKEN not in str(cleaned)
    assert cleaned["n"] == 3
    assert BOT_TOKEN in str(event), "the input must not be mutated"


def test_sentry_uses_the_configured_trace_sample_rate(monkeypatch):
    """SENTRY_TRACES_SAMPLE_RATE reaches sentry_sdk.init (it used to be hard-coded to 1.0)."""
    from unittest.mock import MagicMock

    import sentry_sdk
    from app.config import settings
    from app.observability import setup_observability

    init = MagicMock()
    monkeypatch.setattr(sentry_sdk, "init", init)
    monkeypatch.setattr(settings, "SENTRY_DSN", "https://key@example.invalid/1")
    monkeypatch.setattr(settings, "SENTRY_TRACES_SAMPLE_RATE", 0.25)

    setup_observability("Backend API")

    assert init.call_args.kwargs["traces_sample_rate"] == 0.25


def test_trace_sample_rate_must_be_a_probability():
    from pydantic import ValidationError
    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(SENTRY_TRACES_SAMPLE_RATE=5)
