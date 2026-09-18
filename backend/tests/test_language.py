import pytest
from unittest.mock import AsyncMock
from bot import language


@pytest.fixture(autouse=True)
def clear_cache():
    language.invalidate_language_cache()
    yield
    language.invalidate_language_cache()


@pytest.mark.asyncio
async def test_defaults_to_french_when_unset():
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = None

    result = await language.get_active_language(backend_client=mock_client)

    assert result == "fr"


@pytest.mark.asyncio
async def test_returns_configured_language():
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "en"

    result = await language.get_active_language(backend_client=mock_client)

    assert result == "en"


@pytest.mark.asyncio
async def test_unsupported_language_falls_back_to_french():
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "de"

    result = await language.get_active_language(backend_client=mock_client)

    assert result == "fr"


@pytest.mark.asyncio
async def test_result_is_cached():
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "en"

    await language.get_active_language(backend_client=mock_client)
    await language.get_active_language(backend_client=mock_client)

    mock_client.get_setting.assert_called_once()


@pytest.mark.asyncio
async def test_invalidate_forces_recheck():
    mock_client = AsyncMock()
    mock_client.get_setting.return_value = "en"
    await language.get_active_language(backend_client=mock_client)

    language.invalidate_language_cache()
    await language.get_active_language(backend_client=mock_client)

    assert mock_client.get_setting.call_count == 2


@pytest.mark.asyncio
async def test_lookup_error_falls_back_to_french():
    mock_client = AsyncMock()
    mock_client.get_setting.side_effect = Exception("network error")

    result = await language.get_active_language(backend_client=mock_client)

    assert result == "fr"
