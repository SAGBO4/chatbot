import logging
from unittest.mock import AsyncMock

import pytest

from bot.messaging import call_with_markdown_fallback


@pytest.mark.asyncio
async def test_markdown_is_used_first_and_the_result_returned():
    send = AsyncMock(return_value="sent")

    result = await call_with_markdown_fallback(send, "hello *x*", reply_markup="kb", what="answer")

    assert result == "sent"
    send.assert_awaited_once_with("hello *x*", parse_mode="Markdown", reply_markup="kb")


@pytest.mark.asyncio
async def test_a_rejected_markdown_message_is_retried_without_parse_mode(caplog):
    send = AsyncMock(side_effect=[Exception("can't parse entities"), "sent"])

    with caplog.at_level(logging.WARNING):
        result = await call_with_markdown_fallback(send, "hello", reply_markup="kb", what="answer")

    assert result == "sent"
    assert send.await_args_list[1].args == ("hello",) and send.await_args_list[1].kwargs == {"reply_markup": "kb"}
    assert "answer failed in Markdown, retrying in plain text" in caplog.text


@pytest.mark.asyncio
async def test_plain_overrides_replace_arguments_in_the_retry_only():
    send = AsyncMock(side_effect=[Exception("bad"), "sent"])

    await call_with_markdown_fallback(send, chat_id=5, text="*card*", plain_overrides={"text": "card"}, what="card")

    assert send.await_args_list[0].kwargs == {"chat_id": 5, "text": "*card*", "parse_mode": "Markdown"}
    assert send.await_args_list[1].kwargs == {"chat_id": 5, "text": "card"}


@pytest.mark.asyncio
async def test_a_failing_retry_is_raised_by_default():
    send = AsyncMock(side_effect=[Exception("markdown"), RuntimeError("network down")])

    with pytest.raises(RuntimeError, match="network down"):
        await call_with_markdown_fallback(send, "hello", what="answer")


@pytest.mark.asyncio
async def test_a_failing_retry_can_be_swallowed_and_logged_at_the_requested_level(caplog):
    send = AsyncMock(side_effect=[Exception("markdown"), RuntimeError("network down")])

    with caplog.at_level(logging.WARNING):
        result = await call_with_markdown_fallback(
            send, "hello", what="card", swallow_failure=True, failure_level=logging.ERROR
        )

    assert result is None
    assert any(r.levelno == logging.ERROR and "card failed in plain text too" in r.getMessage() for r in caplog.records)
