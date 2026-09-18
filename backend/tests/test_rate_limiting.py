import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, User, Chat
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from bot.middlewares.throttling import ThrottlingMiddleware
from backend.limiter import Limiter, RateLimitExceeded, _rate_limit_exceeded_handler


@pytest.mark.asyncio
async def test_throttling_middleware_allowed_burst():
    """Verify that messages within the allowed burst limit pass through to the handler."""
    middleware = ThrottlingMiddleware(rate_limit=5, window_seconds=10.0)
    handler = AsyncMock(return_value="handled")

    user = User(id=1001, is_bot=False, first_name="Alice")
    chat = Chat(id=1001, type="private")

    for _ in range(5):
        msg = MagicMock(spec=Message)
        msg.from_user = user
        msg.chat = chat
        msg.answer = AsyncMock()

        result = await middleware(handler, msg, {})
        assert result == "handled"
        msg.answer.assert_not_called()

    assert handler.call_count == 5


@pytest.mark.asyncio
async def test_throttling_middleware_exceeded_and_cooldown():
    """Verify that messages exceeding rate limit are dropped and receive warning."""
    middleware = ThrottlingMiddleware(rate_limit=3, window_seconds=10.0, warning_cooldown=5.0)
    handler = AsyncMock(return_value="handled")

    user = User(id=2002, is_bot=False, first_name="Bob")
    chat = Chat(id=2002, type="private")

    # Send 3 allowed messages
    for _ in range(3):
        msg = MagicMock(spec=Message)
        msg.from_user = user
        msg.chat = chat
        msg.answer = AsyncMock()
        await middleware(handler, msg, {})

    assert handler.call_count == 3

    # 4th message should be throttled and answered with warning
    msg4 = MagicMock(spec=Message)
    msg4.from_user = user
    msg4.chat = chat
    msg4.answer = AsyncMock()
    result4 = await middleware(handler, msg4, {})

    assert result4 is None
    assert handler.call_count == 3  # handler was not called
    msg4.answer.assert_called_once()
    assert "patienter" in msg4.answer.call_args[0][0].lower()

    # 5th message right away: still throttled, but warning in cooldown
    msg5 = MagicMock(spec=Message)
    msg5.from_user = user
    msg5.chat = chat
    msg5.answer = AsyncMock()
    result5 = await middleware(handler, msg5, {})

    assert result5 is None
    assert handler.call_count == 3
    msg5.answer.assert_not_called()  # silenced during cooldown


@pytest.mark.asyncio
async def test_throttling_middleware_user_isolation():
    """Verify that throttling one user does not affect another user."""
    middleware = ThrottlingMiddleware(rate_limit=2, window_seconds=10.0)
    handler = AsyncMock(return_value="handled")

    user1 = User(id=1, is_bot=False, first_name="User1")
    user2 = User(id=2, is_bot=False, first_name="User2")

    # Exceed limit for user1
    for _ in range(3):
        msg = MagicMock(spec=Message)
        msg.from_user = user1
        msg.answer = AsyncMock()
        await middleware(handler, msg, {})

    assert handler.call_count == 2

    # User2 sends message - should pass
    msg2 = MagicMock(spec=Message)
    msg2.from_user = user2
    msg2.answer = AsyncMock()
    res2 = await middleware(handler, msg2, {})

    assert res2 == "handled"
    assert handler.call_count == 3


@pytest.mark.asyncio
async def test_throttling_non_message_event():
    """Verify non-Message events pass through untouched."""
    middleware = ThrottlingMiddleware(rate_limit=1, window_seconds=10.0)
    handler = AsyncMock(return_value="pass")

    non_msg_event = MagicMock()  # not isinstance Message
    result = await middleware(handler, non_msg_event, {})
    assert result == "pass"
    assert handler.call_count == 1


def test_fastapi_rate_limiter():
    """Verify FastAPI RateLimiter returns 429 when threshold is reached."""
    app = FastAPI()
    custom_limiter = Limiter(key_func=lambda *args, **kwargs: "test_client")
    app.state.limiter = custom_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.get("/limited-endpoint")
    @custom_limiter.limit("3/minute")
    def limited_endpoint(request: Request):
        return {"status": "ok"}

    client = TestClient(app)

    # First 3 requests succeed
    for _ in range(3):
        res = client.get("/limited-endpoint")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}

    res4 = client.get("/limited-endpoint")
    assert res4.status_code == 429
    data = res4.json() if "json" in res4.headers.get("content-type", "") else {}
    msg = data.get("detail") or data.get("error") or res4.text
    assert "rate limit exceeded" in str(msg).lower()


def test_resolve_ticket_rate_limiting(monkeypatch):
    """Verify that ticket resolution endpoint is rate limited."""
    from backend.main import app as main_app
    from backend.config import settings

    test_key = "test-api-key-rate-limit-123"
    monkeypatch.setattr(settings, "API_KEY", test_key)

    client = TestClient(main_app)
    headers = {"X-API-Key": test_key}

    # Call 16 times in succession (limit is 15/minute)
    responses = []
    for _ in range(16):
        res = client.post(
            "/api/tickets/99999/resolve",
            json={"solution": "test fix", "resolved_by": "tester"},
            headers=headers,
        )
        responses.append(res.status_code)

    # 16th request must trigger 429 rate limit exceeded
    assert 429 in responses, f"Expected 429 in responses, got {responses}"
