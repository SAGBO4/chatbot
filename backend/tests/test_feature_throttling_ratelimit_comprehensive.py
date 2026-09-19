import time
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import CallbackQuery, Message, User, Chat

from bot.middlewares.throttling import ThrottlingMiddleware
from app.limiter import limiter


@pytest.mark.asyncio
async def test_throttling_messages_under_rate_limit_are_allowed():
    """
    1. FUNCTIONAL:
    Messages under the limit (4 messages with a limit of 5)
    must all be passed to the handler.
    """
    middleware = ThrottlingMiddleware(rate_limit=5, window_seconds=10.0)
    handler = AsyncMock(return_value="OK")

    user = MagicMock(spec=User, id=42)
    message = MagicMock(spec=Message, from_user=user)

    for _ in range(4):
        res = await middleware(handler, message, {})
        assert res == "OK"

    assert handler.call_count == 4


@pytest.mark.asyncio
async def test_throttling_applies_to_callback_queries_too():
    """
    2. SECURITY:
    Callback queries (inline button clicks, e.g. "resolve:no") are
    subject to the same limit as messages - otherwise a user could
    bypass all throttling by spamming a button instead of text.
    """
    middleware = ThrottlingMiddleware(rate_limit=3, window_seconds=10.0)
    handler = AsyncMock(return_value="OK")

    user = MagicMock(spec=User, id=77)
    callback = MagicMock(spec=CallbackQuery, from_user=user, data="resolve:no")
    callback.answer = AsyncMock()

    for _ in range(3):
        res = await middleware(handler, callback, {})
        assert res == "OK"

    # 4th click within the window is dropped, never reaching the handler
    res = await middleware(handler, callback, {})
    assert res is None
    assert handler.call_count == 3
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_throttling_excess_messages_dropped_and_warning_sent():
    """
    1. FUNCTIONAL & SECURITY:
    The 6th message sent within the window exceeds the limit (5).
    It must be blocked (returns None without calling the handler) and a warning is sent.
    """
    middleware = ThrottlingMiddleware(rate_limit=5, window_seconds=10.0, warning_cooldown=5.0)
    handler = AsyncMock(return_value="OK")

    user = MagicMock(spec=User, id=42)
    message = MagicMock(spec=Message, from_user=user)
    message.answer = AsyncMock()

    # 5 messages allowed
    for _ in range(5):
        res = await middleware(handler, message, {})
        assert res == "OK"

    # 6th message blocked
    res_blocked = await middleware(handler, message, {})
    assert res_blocked is None
    assert handler.call_count == 5

    # Warning sent to the user
    message.answer.assert_called_once()
    assert "Veuillez patienter" in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_throttling_warning_cooldown_prevents_repeated_warning_spam():
    """
    1. FUNCTIONAL:
    During the warning cooldown period, excess messages
    are silently ignored without spamming the user with warning messages.
    """
    middleware = ThrottlingMiddleware(rate_limit=2, window_seconds=10.0, warning_cooldown=5.0)
    handler = AsyncMock(return_value="OK")

    user = MagicMock(spec=User, id=42)
    message = MagicMock(spec=Message, from_user=user)
    message.answer = AsyncMock()

    # 2 allowed
    await middleware(handler, message, {})
    await middleware(handler, message, {})

    # 3rd: blocked + warning 1
    await middleware(handler, message, {})
    assert message.answer.call_count == 1

    # 4th: blocked, but no new warning (cooldown active)
    await middleware(handler, message, {})
    assert message.answer.call_count == 1


@pytest.mark.asyncio
async def test_throttling_per_user_isolation_one_user_limit_does_not_block_another_user():
    """
    2. SECURITY - User isolation:
    User A exceeding their quota must never block user B.
    """
    middleware = ThrottlingMiddleware(rate_limit=2, window_seconds=10.0)
    handler = AsyncMock(return_value="OK")

    user_a = MagicMock(spec=User, id=101)
    user_b = MagicMock(spec=User, id=202)

    msg_a = MagicMock(spec=Message, from_user=user_a)
    msg_a.answer = AsyncMock()
    msg_b = MagicMock(spec=Message, from_user=user_b)
    msg_b.answer = AsyncMock()

    # User A uses their 2 requests and gets blocked on the 3rd
    await middleware(handler, msg_a, {})
    await middleware(handler, msg_a, {})
    res_a3 = await middleware(handler, msg_a, {})
    assert res_a3 is None

    # User B must be able to send their messages normally
    res_b1 = await middleware(handler, msg_b, {})
    assert res_b1 == "OK"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_throttling_sliding_window_expiration_allows_new_messages():
    """
    1. FUNCTIONAL & ROBUSTNESS - Sliding window expiration (marked @pytest.mark.slow):
    Once the time window has expired, the user may send messages again.
    """
    # Very short 0.2s window for the test
    middleware = ThrottlingMiddleware(rate_limit=1, window_seconds=0.2)
    handler = AsyncMock(return_value="OK")

    user = MagicMock(spec=User, id=77)
    msg = MagicMock(spec=Message, from_user=user)
    msg.answer = AsyncMock()

    # 1er message OK
    res1 = await middleware(handler, msg, {})
    assert res1 == "OK"

    # Right after: blocked
    res2 = await middleware(handler, msg, {})
    assert res2 is None

    # Wait for the window to expire
    time.sleep(0.25)

    # New message allowed
    res3 = await middleware(handler, msg, {})
    assert res3 == "OK"


@pytest.mark.asyncio
async def test_ratelimit_backend_tickets_exceeding_limit_returns_429(app_test_env):
    """
    1. FUNCTIONAL / 2. SECURITY - FastAPI backend limiter:
    The POST /api/tickets endpoint is limited to 10/minute.
    The 11th request must return 429 Too Many Requests.
    """
    client, _, _ = app_test_env
    limiter.enabled = True
    limiter.reset()

    try:
        # Send 10 valid requests
        for i in range(10):
            resp = await client.post(
                "/api/tickets",
                json={"user_id": 1, "question": f"Question {i}"},
            )
            assert resp.status_code == 201

        # 11th request -> 429
        resp_blocked = await client.post(
            "/api/tickets",
            json={"user_id": 1, "question": "Question 11 excédentaire"},
        )
        assert resp_blocked.status_code == 429
        data = resp_blocked.json()
        assert "Rate limit exceeded" in data["detail"]
        assert "error" in data
    finally:
        limiter.reset()
        limiter.enabled = False


@pytest.mark.asyncio
async def test_throttling_forgets_users_who_have_been_idle(monkeypatch):
    """
    Without a purge, user_timestamps and last_warning_time grow with every user
    ever seen (a slow memory leak on a public bot). A user idle beyond the
    window must be forgotten, without changing the behaviour for the others.
    """
    clock = [1000.0]
    monkeypatch.setattr("bot.middlewares.throttling.time.time", lambda: clock[0])
    middleware = ThrottlingMiddleware(rate_limit=2, window_seconds=10.0, warning_cooldown=5.0)
    handler = AsyncMock(return_value="OK")

    def message_from(user_id):
        message = MagicMock(spec=Message, from_user=MagicMock(spec=User, id=user_id))
        message.answer = AsyncMock()
        return message

    # user 1 gets throttled (warning recorded), users 2 and 3 send one message each
    for _ in range(3):
        await middleware(handler, message_from(1), {})
    await middleware(handler, message_from(2), {})
    await middleware(handler, message_from(3), {})
    assert set(middleware.user_timestamps) == {1, 2, 3}
    assert set(middleware.last_warning_time) == {1}

    # 60 s later only user 4 writes: the three idle users are dropped
    clock[0] += 60.0
    assert await middleware(handler, message_from(4), {}) == "OK"
    assert set(middleware.user_timestamps) == {4}
    assert middleware.last_warning_time == {}

    # a returning user starts from a clean slate
    assert await middleware(handler, message_from(1), {}) == "OK"
