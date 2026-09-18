import pytest
import httpx
from backend.main import app
from backend.database import get_db
from backend.config import settings
from bot.api_client import BackendClient

TEST_API_KEY = "test-api-key-admin-settings"


@pytest.mark.asyncio
async def test_backend_client_set_and_get_setting(app_test_env, monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", TEST_API_KEY)
    _, session_maker, engine = app_test_env
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as httpx_client:
        bc = BackendClient(base_url="http://testserver", client=httpx_client)

        assert await bc.get_setting("community_group_id") is None
        result = await bc.set_setting("community_group_id", "-100777", updated_by="owner")
        assert result["value"] == "-100777"
        assert await bc.get_setting("community_group_id") == "-100777"


@pytest.mark.asyncio
async def test_backend_client_whitelist_flow(app_test_env, monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", TEST_API_KEY)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as httpx_client:
        bc = BackendClient(base_url="http://testserver", client=httpx_client)

        assert await bc.is_whitelisted(42) is False
        await bc.whitelist_add(42, added_by="owner")
        assert await bc.is_whitelisted(42) is True
        removed = await bc.whitelist_remove(42)
        assert removed is True
        assert await bc.is_whitelisted(42) is False
        assert await bc.whitelist_remove(42) is False
