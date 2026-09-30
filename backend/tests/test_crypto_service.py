import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.crypto_service import CryptoService


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


@pytest.mark.asyncio
async def test_api_key_header_is_passed_when_configured(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "COINGECKO_API_KEY", "CG-TEST-KEY")
    client = AsyncMock()
    client.get.return_value = make_response(
        200, {"bitcoin": {"usd": 50000, "usd_24h_change": 0, "usd_market_cap": 0, "usd_24h_vol": 0}}
    )
    await CryptoService.get_market_data("btc", client=client)
    call_kwargs = client.get.call_args.kwargs
    assert call_kwargs.get("headers", {}).get("x-cg-demo-api-key") == "CG-TEST-KEY"


@pytest.mark.asyncio
async def test_no_api_key_header_when_not_configured(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "COINGECKO_API_KEY", None)
    client = AsyncMock()
    client.get.return_value = make_response(
        200, {"bitcoin": {"usd": 50000, "usd_24h_change": 0, "usd_market_cap": 0, "usd_24h_vol": 0}}
    )
    await CryptoService.get_market_data("btc", client=client)
    call_kwargs = client.get.call_args.kwargs
    assert "x-cg-demo-api-key" not in call_kwargs.get("headers", {})


@pytest.mark.asyncio
async def test_api_key_header_is_stripped_when_padded(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "COINGECKO_API_KEY", "  CG-TEST-KEY-PADDED  ")
    client = AsyncMock()
    client.get.return_value = make_response(
        200, {"bitcoin": {"usd": 50000, "usd_24h_change": 0, "usd_market_cap": 0, "usd_24h_vol": 0}}
    )
    await CryptoService.get_market_data("btc", client=client)
    call_kwargs = client.get.call_args.kwargs
    assert call_kwargs.get("headers", {}).get("x-cg-demo-api-key") == "CG-TEST-KEY-PADDED"


@pytest.mark.asyncio
async def test_stale_cache_returned_when_shared_client_fails(monkeypatch):
    import time
    CryptoService._cache["bitcoin"] = (
        {"price_usd": 60000.0, "change_24h_pct": 1.0, "market_cap_usd": 1e12, "volume_24h_usd": 1e10},
        time.time() - 3600,  # 1 hour old (stale)
    )
    mock_shared = AsyncMock()
    mock_shared.get.side_effect = httpx.ConnectError("Network down")
    CryptoService.set_shared_client(mock_shared)
    try:
        result = await CryptoService.get_market_data("btc")
        assert result is not None
        assert result["price_usd"] == 60000.0
    finally:
        CryptoService.set_shared_client(None)


@pytest.mark.asyncio
async def test_epic_fallback_returned_when_provider_fails_and_no_cache():
    mock_shared = AsyncMock()
    mock_shared.get.side_effect = httpx.TimeoutException("timeout")
    CryptoService.set_shared_client(mock_shared)
    try:
        result = await CryptoService.get_market_data("epic")
        assert result is not None
        assert result["price_usd"] == 0.42
    finally:
        CryptoService.set_shared_client(None)


@pytest.mark.asyncio
async def test_ripple_and_stellar_fallback_returned_when_provider_fails():
    mock_shared = AsyncMock()
    mock_shared.get.side_effect = httpx.ConnectError("Connection refused")
    CryptoService.set_shared_client(mock_shared)
    try:
        xrp = await CryptoService.get_market_data("xrp")
        assert xrp is not None
        assert xrp["price_usd"] == 0.585

        xlm = await CryptoService.get_market_data("xlm")
        assert xlm is not None
        assert xlm["price_usd"] == 0.22
    finally:
        CryptoService.set_shared_client(None)


@pytest.mark.parametrize("status_code", [401, 429, 500, 502, 503])
@pytest.mark.asyncio
async def test_provider_http_error_statuses_return_fallback_when_using_shared_client(status_code):
    mock_shared = AsyncMock()
    mock_shared.get.return_value = make_response(status_code, text=f"Error {status_code}")
    CryptoService.set_shared_client(mock_shared)
    try:
        result = await CryptoService.get_market_data("btc")
        assert result is not None
        assert result["price_usd"] == 68450.00
    finally:
        CryptoService.set_shared_client(None)


@pytest.mark.asyncio
async def test_unknown_or_unsupported_fallback_asset_returns_none_on_failure():
    mock_shared = AsyncMock()
    mock_shared.get.side_effect = httpx.TimeoutException("timeout")
    CryptoService.set_shared_client(mock_shared)
    try:
        # 'shib' is a valid symbol in SYMBOL_TO_COINGECKO_ID, but not in FALLBACK_MARKET_DATA
        result = await CryptoService.get_market_data("shib")
        assert result is None
    finally:
        CryptoService.set_shared_client(None)


@pytest.mark.asyncio
async def test_cache_ttl_120s_serves_without_second_call():
    import time
    from app.config import settings

    mock_shared = AsyncMock()
    mock_shared.get.return_value = make_response(
        200, {"bitcoin": {"usd": 70000, "usd_24h_change": 1.2, "usd_market_cap": 1.3e12, "usd_24h_vol": 2e10}}
    )
    CryptoService.set_shared_client(mock_shared)
    try:
        # First call hits provider
        first = await CryptoService.get_market_data("btc")
        assert first["price_usd"] == 70000
        assert mock_shared.get.call_count == 1

        # Second call within TTL (120s) uses cache
        second = await CryptoService.get_market_data("btc")
        assert second["price_usd"] == 70000
        assert mock_shared.get.call_count == 1

        # Simulate time passage past TTL
        cached_data, _ = CryptoService._cache["bitcoin"]
        CryptoService._cache["bitcoin"] = (cached_data, time.time() - (settings.CRYPTO_CACHE_TTL_SECONDS + 5))

        mock_shared.get.return_value = make_response(
            200, {"bitcoin": {"usd": 71000, "usd_24h_change": 2.0, "usd_market_cap": 1.4e12, "usd_24h_vol": 2.5e10}}
        )
        third = await CryptoService.get_market_data("btc")
        assert third["price_usd"] == 71000
        assert mock_shared.get.call_count == 2
    finally:
        CryptoService.set_shared_client(None)


def test_all_109_symbols_map_to_valid_non_empty_coingecko_ids():
    from app.services.crypto_service import SYMBOL_TO_COINGECKO_ID
    assert len(SYMBOL_TO_COINGECKO_ID) >= 109
    for symbol, asset_id in SYMBOL_TO_COINGECKO_ID.items():
        assert isinstance(symbol, str) and symbol == symbol.lower().strip()
        assert isinstance(asset_id, str) and len(asset_id) > 0
        assert CryptoService.resolve_asset_id(symbol) == asset_id
        assert CryptoService.resolve_asset_id(symbol.upper()) == asset_id


