import pytest
from unittest.mock import AsyncMock
from bot import access_control


@pytest.fixture(autouse=True)
def clear_cache():
    access_control.invalidate_whitelist_cache()
    yield
    access_control.invalidate_whitelist_cache()


@pytest.mark.asyncio
async def test_owner_is_authorized_without_whitelist_lookup(monkeypatch):
    monkeypatch.setattr("backend.config.settings.BOT_OWNER_TELEGRAM_ID", 999)
    mock_client = AsyncMock()

    result = await access_control.is_authorized(999, backend_client=mock_client)

    assert result is True
    mock_client.is_whitelisted.assert_not_called()


@pytest.mark.asyncio
async def test_whitelisted_non_owner_is_authorized(monkeypatch):
    monkeypatch.setattr("backend.config.settings.BOT_OWNER_TELEGRAM_ID", 999)
    mock_client = AsyncMock()
    mock_client.is_whitelisted.return_value = True

    result = await access_control.is_authorized(42, backend_client=mock_client)

    assert result is True
    mock_client.is_whitelisted.assert_called_once_with(42)


@pytest.mark.asyncio
async def test_non_owner_non_whitelisted_is_rejected(monkeypatch):
    monkeypatch.setattr("backend.config.settings.BOT_OWNER_TELEGRAM_ID", 999)
    mock_client = AsyncMock()
    mock_client.is_whitelisted.return_value = False

    result = await access_control.is_authorized(1, backend_client=mock_client)

    assert result is False


@pytest.mark.asyncio
async def test_whitelist_result_is_cached_and_avoids_second_call(monkeypatch):
    monkeypatch.setattr("backend.config.settings.BOT_OWNER_TELEGRAM_ID", 999)
    mock_client = AsyncMock()
    mock_client.is_whitelisted.return_value = True

    first = await access_control.is_authorized(42, backend_client=mock_client)
    second = await access_control.is_authorized(42, backend_client=mock_client)

    assert first is True
    assert second is True
    mock_client.is_whitelisted.assert_called_once()


@pytest.mark.asyncio
async def test_invalidate_whitelist_cache_forces_recheck(monkeypatch):
    monkeypatch.setattr("backend.config.settings.BOT_OWNER_TELEGRAM_ID", 999)
    mock_client = AsyncMock()
    mock_client.is_whitelisted.return_value = True
    await access_control.is_authorized(42, backend_client=mock_client)

    access_control.invalidate_whitelist_cache(42)
    await access_control.is_authorized(42, backend_client=mock_client)

    assert mock_client.is_whitelisted.call_count == 2


@pytest.mark.asyncio
async def test_whitelist_lookup_error_defaults_to_unauthorized(monkeypatch):
    monkeypatch.setattr("backend.config.settings.BOT_OWNER_TELEGRAM_ID", 999)
    mock_client = AsyncMock()
    mock_client.is_whitelisted.side_effect = Exception("network error")

    result = await access_control.is_authorized(42, backend_client=mock_client)

    assert result is False
