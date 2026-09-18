import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.services.crypto_service import CryptoService


@pytest.fixture(autouse=True)
def clear_cache():
    CryptoService._cache.clear()
    yield
    CryptoService._cache.clear()


def make_response(status_code=200, json_data=None, text=""):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


@pytest.mark.asyncio
async def test_unrecognized_symbol_returns_none_without_http_call():
    client = AsyncMock()
    result = await CryptoService.get_market_data("notacoin", client=client)
    assert result is None
    client.get.assert_not_called()


@pytest.mark.asyncio
async def test_successful_lookup_returns_expected_fields():
    client = AsyncMock()
    client.get.return_value = make_response(
        200,
        {"bitcoin": {"usd": 65000.5, "usd_24h_change": 2.5, "usd_market_cap": 1.2e12, "usd_24h_vol": 3.4e10}},
    )
    result = await CryptoService.get_market_data("btc", client=client)
    assert result == {
        "price_usd": 65000.5,
        "change_24h_pct": 2.5,
        "market_cap_usd": 1.2e12,
        "volume_24h_usd": 3.4e10,
    }


@pytest.mark.asyncio
async def test_timeout_returns_none():
    client = AsyncMock()
    client.get.side_effect = httpx.TimeoutException("timed out")
    result = await CryptoService.get_market_data("btc", client=client)
    assert result is None


@pytest.mark.asyncio
async def test_rate_limit_returns_none():
    client = AsyncMock()
    client.get.return_value = make_response(429, text="rate limited")
    result = await CryptoService.get_market_data("btc", client=client)
    assert result is None


@pytest.mark.asyncio
async def test_malformed_response_returns_none():
    client = AsyncMock()
    client.get.return_value = make_response(200, {"bitcoin": {"unexpected": "shape"}})
    result = await CryptoService.get_market_data("btc", client=client)
    assert result is None


@pytest.mark.asyncio
async def test_result_is_cached_and_avoids_second_http_call():
    client = AsyncMock()
    client.get.return_value = make_response(
        200, {"bitcoin": {"usd": 100, "usd_24h_change": 1, "usd_market_cap": 1, "usd_24h_vol": 1}}
    )
    first = await CryptoService.get_market_data("btc", client=client)
    second = await CryptoService.get_market_data("btc", client=client)
    assert first == second
    client.get.assert_called_once()
