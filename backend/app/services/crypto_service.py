import time
import logging
from typing import Dict, Optional
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

COINGECKO_SIMPLE_PRICE_URL = "https://api.coingecko.com/api/v3/simple/price"

# Curated symbol -> CoinGecko asset id mapping (see design.md decision 6:
# CoinGecko ids don't map 1:1 from ticker symbols, so this is deliberately a
# small, explicit, extendable table rather than a live search-and-guess).
SYMBOL_TO_COINGECKO_ID: Dict[str, str] = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "firo": "zcoin",
    "usdt": "tether",
    "bnb": "binancecoin",
    "sol": "solana",
    "xrp": "ripple",
    "doge": "dogecoin",
    "ada": "cardano",
    "ltc": "litecoin",
}


class CryptoService:
    _shared_client: Optional[httpx.AsyncClient] = None
    # In-memory TTL cache keyed by coingecko id -> (data, fetched_at).
    _cache: Dict[str, tuple] = {}

    @classmethod
    def set_shared_client(cls, client: Optional[httpx.AsyncClient]) -> None:
        cls._shared_client = client

    @classmethod
    def resolve_asset_id(cls, symbol: str) -> Optional[str]:
        return SYMBOL_TO_COINGECKO_ID.get(symbol.strip().lower())

    @classmethod
    async def get_market_data(
        cls, symbol: str, client: Optional[httpx.AsyncClient] = None
    ) -> Optional[Dict[str, float]]:
        """
        Returns current price/24h change/market cap/24h volume (in USD) for
        the given asset symbol, or None if the symbol is unrecognized or the
        provider call failed (timeout, rate limit, malformed response) - all
        treated as recoverable per the crypto-market-data spec, never raised.
        """
        asset_id = cls.resolve_asset_id(symbol)
        if asset_id is None:
            return None

        cached = cls._cache.get(asset_id)
        if cached is not None:
            data, fetched_at = cached
            if (time.time() - fetched_at) < settings.CRYPTO_CACHE_TTL_SECONDS:
                return data

        effective_client = client or cls._shared_client
        owns_client = effective_client is None
        session = effective_client or httpx.AsyncClient(timeout=settings.CRYPTO_PROVIDER_TIMEOUT_SECONDS)
        try:
            response = await session.get(
                COINGECKO_SIMPLE_PRICE_URL,
                params={
                    "ids": asset_id,
                    "vs_currencies": "usd",
                    "include_market_cap": "true",
                    "include_24hr_vol": "true",
                    "include_24hr_change": "true",
                },
                timeout=settings.CRYPTO_PROVIDER_TIMEOUT_SECONDS,
            )
        except httpx.TimeoutException:
            logger.warning("CoinGecko request timed out for asset %s", asset_id)
            return None
        except httpx.HTTPError as exc:
            logger.warning("CoinGecko request failed for asset %s: %s", asset_id, exc)
            return None
        finally:
            if owns_client:
                await session.aclose()

        if response.status_code == 429:
            logger.warning("CoinGecko rate limit reached for asset %s", asset_id)
            return None
        if response.status_code != 200:
            logger.warning("CoinGecko error %s for asset %s: %s", response.status_code, asset_id, response.text)
            return None

        try:
            payload = response.json()
            asset_data = payload[asset_id]
            result = {
                "price_usd": float(asset_data["usd"]),
                "change_24h_pct": float(asset_data.get("usd_24h_change", 0.0)),
                "market_cap_usd": float(asset_data.get("usd_market_cap", 0.0)),
                "volume_24h_usd": float(asset_data.get("usd_24h_vol", 0.0)),
            }
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("Malformed CoinGecko response for asset %s: %s", asset_id, exc)
            return None

        cls._cache[asset_id] = (result, time.time())
        return result
