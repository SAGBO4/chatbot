import logging
import httpx
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from app.services.crypto_service import SYMBOL_TO_COINGECKO_ID
from bot.api_client import BackendClient
from bot.language import get_active_language
from bot.i18n import t
from typing import Optional

logger = logging.getLogger(__name__)
crypto_router = Router()


def _format_price_reply(symbol: str, data: dict, lang: str) -> str:
    change = data["change_24h_pct"]
    arrow = "📈" if change >= 0 else "📉"
    return t(
        "crypto_price_reply",
        lang,
        symbol=symbol.upper(),
        price=data["price_usd"],
        arrow=arrow,
        change=change,
        market_cap=data["market_cap_usd"],
        volume=data["volume_24h_usd"],
    )


async def _handle_asset_command(message: Message, symbol: str, backend_client: Optional[BackendClient] = None):
    client = backend_client or BackendClient()
    lang = await get_active_language(backend_client=client)
    try:
        data = await client.get_crypto_price(symbol)
    except httpx.HTTPStatusError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            await message.reply(t("crypto_unrecognized_asset", lang, symbol=symbol))
            return
        logger.warning("Crypto lookup failed for %s: %s", symbol, exc)
        await message.reply(t("crypto_unavailable", lang))
        return
    except Exception as exc:
        logger.error("Unexpected error during crypto lookup for %s: %s", symbol, exc)
        await message.reply(t("crypto_unavailable", lang))
        return

    await message.reply(_format_price_reply(symbol, data, lang), parse_mode="Markdown")


def _make_handler(symbol: str):
    async def handler(message: Message, backend_client: Optional[BackendClient] = None):
        await _handle_asset_command(message, symbol, backend_client=backend_client)
    return handler


# Registers one command per curated asset symbol (e.g. /btc, /eth, /firo),
# usable in both private chats and the community group - crypto lookups are
# not ticket/moderation content, so no group scoping is needed here.
for _symbol in SYMBOL_TO_COINGECKO_ID:
    crypto_router.message(Command(_symbol))(_make_handler(_symbol))
