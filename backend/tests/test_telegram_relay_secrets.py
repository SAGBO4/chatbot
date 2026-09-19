"""
The bot token is part of every Telegram Bot API URL, so it must not reach logs or Sentry.

This file name contains "telegram_relay" on purpose: conftest.py only replaces the real HTTP call
in TelegramRelay for other test files.
"""
import logging

import httpx
import pytest

from app.config import settings
from app.observability import SensitiveDataFilter, setup_observability
from app.services.telegram_relay import TelegramRelay

BOT_TOKEN = "123456789:AAH-Secret_Token-Value123"


def _relay_once(caplog_level, monkeypatch):
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": True}))
    TelegramRelay.set_shared_client(httpx.AsyncClient(transport=transport))


@pytest.mark.asyncio
async def test_httpx_request_logs_do_not_contain_the_bot_token(caplog, monkeypatch):
    _relay_once(logging.INFO, monkeypatch)
    setup_observability("test")
    try:
        with caplog.at_level(logging.INFO):
            await TelegramRelay.send_message_to_user(1, "hello")
    finally:
        TelegramRelay.set_shared_client(None)
        for name in ("httpx", "httpcore"):
            logger = logging.getLogger(name)
            logger.filters[:] = [f for f in logger.filters if not isinstance(f, SensitiveDataFilter)]

    assert "HTTP Request" in caplog.text, "httpx no longer logs the request: this test would pass vacuously"
    assert BOT_TOKEN not in caplog.text
    assert "bot[REDACTED]" in caplog.text


@pytest.mark.asyncio
async def test_sentry_events_do_not_contain_the_bot_token(monkeypatch):
    sentry_sdk = pytest.importorskip("sentry_sdk")
    from sentry_sdk.transport import Transport

    events = []

    class Capture(Transport):
        def capture_envelope(self, envelope):
            for item in envelope.items:
                if item.headers.get("type") == "event":
                    events.append(item.payload.json)

    _relay_once(logging.INFO, monkeypatch)
    monkeypatch.setattr(settings, "SENTRY_DSN", "https://key@o0.ingest.sentry.io/1")
    setup_observability("test")
    # setup_observability() starts Sentry with the real transport; restart it with the same hooks
    # and a transport that keeps the events in memory
    client_options = sentry_sdk.get_client().options
    sentry_sdk.init(
        dsn=client_options["dsn"],
        transport=Capture,
        before_send=client_options["before_send"],
        before_breadcrumb=client_options["before_breadcrumb"],
    )
    try:
        await TelegramRelay.send_message_to_user(1, "hello")
        sentry_sdk.capture_message("a later, unrelated error")
        sentry_sdk.flush()
    finally:
        sentry_sdk.get_client().close()
        sentry_sdk.init(dsn=None)
        TelegramRelay.set_shared_client(None)
        for name in ("httpx", "httpcore"):
            logger = logging.getLogger(name)
            logger.filters[:] = [f for f in logger.filters if not isinstance(f, SensitiveDataFilter)]

    assert events, "no Sentry event captured"
    breadcrumbs = [b for e in events for b in (e.get("breadcrumbs") or {}).get("values", [])]
    assert any("api.telegram.org" in str(b) for b in breadcrumbs), "the HTTP breadcrumb is gone: vacuous test"
    assert BOT_TOKEN not in str(events)
