import pytest

from app.observability import redact_secrets, sanitize_url_query, scrub

BOT_TOKEN = "123456789:AAH-Secret_Token-Value123"


@pytest.mark.parametrize(
    "text,forbidden",
    [
        (f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", BOT_TOKEN),
        (f"https://api.telegram.org/file/bot{BOT_TOKEN}/photos/file_1.jpg", BOT_TOKEN),
        ("https://x.test/hook?token=abc123&keep=yes", "abc123"),
        ("https://x.test/hook?a=1&api_key=k3y&password=p4ss&secret=s3c", "k3y"),
    ],
)
def test_redact_secrets_removes_the_secret(text, forbidden):
    assert forbidden not in redact_secrets(text)


def test_redact_secrets_keeps_harmless_parts_readable():
    redacted = redact_secrets(f"POST https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?keep=yes")
    assert redacted == "POST https://api.telegram.org/bot[REDACTED]/sendMessage?keep=yes"


def test_sanitize_url_query_is_still_exposed_from_main():
    from app.main import sanitize_url_query as from_main

    assert from_main is sanitize_url_query


def test_scrub_recurses_into_nested_structures():
    event = {"breadcrumbs": {"values": [{"data": {"url": f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"}}]}, "n": 3}
    cleaned = scrub(event)
    assert BOT_TOKEN not in str(cleaned)
    assert cleaned["n"] == 3
    assert BOT_TOKEN in str(event), "the input must not be mutated"
