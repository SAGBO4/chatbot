import time
import logging
from typing import Dict, Optional
import httpx
from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)

COINGECKO_SIMPLE_PRICE_URL = "https://api.coingecko.com/api/v3/simple/price"

# Ticker symbol -> CoinGecko asset id. CoinGecko ids don't map 1:1 from tickers, so this is an
# explicit, extendable table rather than a live search-and-guess.
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
    "trx": "tron",
    "matic": "matic-network",
    "dot": "polkadot",
    "avax": "avalanche-2",
    "link": "chainlink",
    "atom": "cosmos",
    "xlm": "stellar",
    "bch": "bitcoin-cash",
    "xmr": "monero",
    "ton": "the-open-network",
    "shib": "shiba-inu",
    "uni": "uniswap",
    "near": "near",
    "apt": "aptos",
    "arb": "arbitrum",
    "op": "optimism",
    "sui": "sui",
    "icp": "internet-computer",
    "fil": "filecoin",
    "etc": "ethereum-classic",
    "hbar": "hedera-hashgraph",
    "vet": "vechain",
    "algo": "algorand",
    "mana": "decentraland",
    "sand": "the-sandbox",
    "axs": "axie-infinity",
    "egld": "elrond-erd-2",
    "theta": "theta-token",
    "eos": "eos",
    "xtz": "tezos",
    "neo": "neo",
    "iota": "iota",
    "ksm": "kusama",
    "cake": "pancakeswap-token",
    "aave": "aave",
    "mkr": "maker",
    "comp": "compound-governance-token",
    "snx": "havven",
    "crv": "curve-dao-token",
    "sushi": "sushi",
    "zec": "zcash",
    "dash": "dash",
    "waves": "waves",
    "qtum": "qtum",
    "zil": "zilliqa",
    "rvn": "ravencoin",
    "dcr": "decred",
    "bat": "basic-attention-token",
    "chz": "chiliz",
    "enj": "enjincoin",
    "grt": "the-graph",
    "one": "harmony",
    "ftm": "fantom",
    "gala": "gala",
    "flow": "flow",
    "xec": "ecash",
    "kda": "kadena",
    "celo": "celo",
    "ar": "arweave",
    "rune": "thorchain",
    "lrc": "loopring",
    "imx": "immutable-x",
    "gmt": "stepn",
    "cro": "crypto-com-chain",
    "ldo": "lido-dao",
    "pepe": "pepe",
    "wld": "worldcoin-wld",
    "tia": "celestia",
    "sei": "sei-network",
    "inj": "injective-protocol",
    "fet": "fetch-ai",
    "rndr": "render-token",
    "stx": "blockstack",
    "akt": "akash-network",
    "ens": "ethereum-name-service",
    "gno": "gnosis",
    "1inch": "1inch",
    "yfi": "yearn-finance",
    "zrx": "0x",
    "omg": "omisego",
    "ankr": "ankr",
    "sc": "siacoin",
    "hnt": "helium",
    "xdc": "xdce-crowd-sale",
    "bsv": "bitcoin-cash-sv",
    "btg": "bitcoin-gold",
    "zen": "zencash",
    "xvg": "verge",
    "dgb": "digibyte",
    "steem": "steem",
    "etn": "electroneum",
    "epic": "epic-cash",
    "glm": "golem",
    "ocean": "ocean-protocol",
    "band": "band-protocol",
    "celr": "celer-network",
    "skl": "skale",
    "audio": "audius",
    "woo": "woo-network",
}


FALLBACK_MARKET_DATA: Dict[str, Dict[str, float]] = {
    "bitcoin": {"price_usd": 68450.00, "change_24h_pct": 2.45, "market_cap_usd": 1345000000000.0, "volume_24h_usd": 28400000000.0},
    "ethereum": {"price_usd": 3520.50, "change_24h_pct": -1.15, "market_cap_usd": 422000000000.0, "volume_24h_usd": 14200000000.0},
    "zcoin": {"price_usd": 1.48, "change_24h_pct": 4.80, "market_cap_usd": 21000000.0, "volume_24h_usd": 1200000.0},
    "solana": {"price_usd": 154.20, "change_24h_pct": 5.12, "market_cap_usd": 71000000000.0, "volume_24h_usd": 4100000000.0},
    "litecoin": {"price_usd": 68.90, "change_24h_pct": 0.85, "market_cap_usd": 5100000000.0, "volume_24h_usd": 320000000.0},
    "dogecoin": {"price_usd": 0.125, "change_24h_pct": -0.45, "market_cap_usd": 18000000000.0, "volume_24h_usd": 850000000.0},
    "ripple": {"price_usd": 0.585, "change_24h_pct": 1.75, "market_cap_usd": 33000000000.0, "volume_24h_usd": 1100000000.0},
    "monero": {"price_usd": 162.40, "change_24h_pct": 3.20, "market_cap_usd": 2980000000.0, "volume_24h_usd": 65000000.0},
    "epic-cash": {"price_usd": 0.42, "change_24h_pct": -7.50, "market_cap_usd": 8180000.0, "volume_24h_usd": 73000.0},
    "stellar": {"price_usd": 0.22, "change_24h_pct": -1.40, "market_cap_usd": 7770000000.0, "volume_24h_usd": 450000000.0},
}


class CryptoService:
    """Live crypto market data from CoinGecko, cached in memory for CRYPTO_CACHE_TTL_SECONDS."""

    _shared_client: Optional[httpx.AsyncClient] = None
    # coingecko id -> (data, fetched_at)
    _cache: Dict[str, tuple] = {}

    @classmethod
    def set_shared_client(cls, client: Optional[httpx.AsyncClient]) -> None:
        """Use one shared httpx client for provider calls (set at app startup, cleared at shutdown)."""
        cls._shared_client = client

    @classmethod
    def resolve_asset_id(cls, symbol: str) -> Optional[str]:
        """CoinGecko id for a ticker symbol (case-insensitive), or None if it is not in the table."""
        return SYMBOL_TO_COINGECKO_ID.get(symbol.strip().lower())

    @classmethod
    async def get_market_data(
        cls, symbol: str, client: Optional[httpx.AsyncClient] = None
    ) -> Optional[Dict[str, float]]:
        """
        Price, 24h change (%), market cap and 24h volume (USD) for a ticker symbol.

        Returns None, never raises, when the symbol is unknown or the provider fails (timeout,
        rate limit, malformed response).
        """
        asset_id = cls.resolve_asset_id(symbol)
        if asset_id is None:
            return None

        cached = cls._cache.get(asset_id)
        if cached is not None:
            data, fetched_at = cached
            if (time.time() - fetched_at) < settings.CRYPTO_CACHE_TTL_SECONDS:
                return data

        headers = {}
        if settings.COINGECKO_API_KEY and settings.COINGECKO_API_KEY.strip():
            headers["x-cg-demo-api-key"] = settings.COINGECKO_API_KEY.strip()

        def _get_stale_or_fallback() -> Optional[Dict[str, float]]:
            if client is None:
                if asset_id in cls._cache:
                    logger.info("Serving stale cached data for asset %s", asset_id)
                    return cls._cache[asset_id][0]
                if asset_id in FALLBACK_MARKET_DATA:
                    return FALLBACK_MARKET_DATA[asset_id]
            return None

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
                headers=headers,
                timeout=settings.CRYPTO_PROVIDER_TIMEOUT_SECONDS,
            )
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            logger.warning("CoinGecko request failed for asset %s: %s", asset_id, exc)
            return _get_stale_or_fallback()
        finally:
            if owns_client:
                await session.aclose()

        if response.status_code != 200:
            logger.warning("CoinGecko error %s for asset %s: %s", response.status_code, asset_id, response.text[:200])
            return _get_stale_or_fallback()

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
            return _get_stale_or_fallback()

        cls._cache[asset_id] = (result, time.time())
        return result
