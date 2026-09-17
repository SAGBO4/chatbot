import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import User, Chat, Message

from bot.handlers.crypto_handlers import _handle_asset_command


def make_message(chat_type="private"):
    message = MagicMock(spec=Message)
    message.chat = MagicMock(spec=Chat, id=1, type=chat_type)
    message.from_user = MagicMock(spec=User, id=1, username="alice", first_name="Alice")
    message.reply = AsyncMock()
    return message


@pytest.mark.asyncio
async def test_known_asset_lookup_formats_reply():
    message = make_message()
    mock_client = AsyncMock()
    mock_client.get_crypto_price.return_value = {
        "symbol": "btc",
        "price_usd": 65000.5,
        "change_24h_pct": 2.5,
        "market_cap_usd": 1.2e12,
        "volume_24h_usd": 3.4e10,
    }

    await _handle_asset_command(message, "btc", backend_client=mock_client)

    mock_client.get_crypto_price.assert_called_once_with("btc")
    message.reply.assert_called_once()
    reply_text = message.reply.call_args[0][0]
    assert "BTC" in reply_text
    assert "65,000.50" in reply_text
    assert "2.50%" in reply_text


@pytest.mark.asyncio
async def test_unrecognized_asset_replies_not_found():
    message = make_message()
    mock_client = AsyncMock()
    response = MagicMock(status_code=404)
    mock_client.get_crypto_price.side_effect = httpx.HTTPStatusError("404", request=MagicMock(), response=response)

    await _handle_asset_command(message, "notacoin", backend_client=mock_client)

    assert "non reconnu" in message.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_provider_unavailable_replies_temporarily_unavailable():
    message = make_message()
    mock_client = AsyncMock()
    response = MagicMock(status_code=503)
    mock_client.get_crypto_price.side_effect = httpx.HTTPStatusError("503", request=MagicMock(), response=response)

    await _handle_asset_command(message, "btc", backend_client=mock_client)

    assert "temporairement indisponibles" in message.reply.call_args[0][0]


@pytest.mark.asyncio
async def test_usable_in_community_group_chat_too():
    message = make_message(chat_type="supergroup")
    mock_client = AsyncMock()
    mock_client.get_crypto_price.return_value = {
        "symbol": "eth", "price_usd": 3000.0, "change_24h_pct": -1.2,
        "market_cap_usd": 3.5e11, "volume_24h_usd": 1.1e10,
    }

    await _handle_asset_command(message, "eth", backend_client=mock_client)

    mock_client.get_crypto_price.assert_called_once_with("eth")
    message.reply.assert_called_once()
