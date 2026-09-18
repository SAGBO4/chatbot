import pytest
from unittest.mock import AsyncMock
from bot import group_scope


@pytest.fixture(autouse=True)
def clear_cache():
    group_scope.invalidate_community_group_cache()
    yield
    group_scope.invalidate_community_group_cache()


@pytest.mark.asyncio
async def test_no_community_group_configured_returns_none():
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = None

    result = await group_scope.get_community_group_id(backend_client=mock_client)

    assert result is None


@pytest.mark.asyncio
async def test_configured_group_is_resolved():
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "-100555"

    result = await group_scope.get_community_group_id(backend_client=mock_client)

    assert result == -100555


@pytest.mark.asyncio
async def test_result_is_cached_and_avoids_second_call():
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "-100555"

    first = await group_scope.get_community_group_id(backend_client=mock_client)
    second = await group_scope.get_community_group_id(backend_client=mock_client)

    assert first == second == -100555
    mock_client.get_setting.assert_called_once()


@pytest.mark.asyncio
async def test_invalidate_cache_forces_recheck():
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "-100555"
    await group_scope.get_community_group_id(backend_client=mock_client)

    group_scope.invalidate_community_group_cache()
    await group_scope.get_community_group_id(backend_client=mock_client)

    assert mock_client.get_setting.call_count == 2


@pytest.mark.asyncio
async def test_lookup_error_resolves_to_none():
    mock_client = AsyncMock()
    mock_client.get_setting.side_effect = Exception("network error")

    result = await group_scope.get_community_group_id(backend_client=mock_client)

    assert result is None


@pytest.mark.asyncio
async def test_is_community_group_chat_matches_configured_group():
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "-100555"

    assert await group_scope.is_community_group_chat(-100555, backend_client=mock_client) is True
    assert await group_scope.is_community_group_chat(-999999, backend_client=mock_client) is False


@pytest.mark.asyncio
async def test_is_community_group_chat_false_when_unconfigured():
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = None

    assert await group_scope.is_community_group_chat(-100555, backend_client=mock_client) is False


@pytest.mark.asyncio
async def test_reconfiguration_reflected_after_cache_invalidation():
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "-100555"
    assert await group_scope.is_community_group_chat(-100555, backend_client=mock_client) is True

    # Reconfigure to a different group and invalidate the cache, as
    # /setup_community does on a successful change.
    mock_client.get_setting.return_value = "-100999"
    group_scope.invalidate_community_group_cache()

    assert await group_scope.is_community_group_chat(-100555, backend_client=mock_client) is False
    assert await group_scope.is_community_group_chat(-100999, backend_client=mock_client) is True
