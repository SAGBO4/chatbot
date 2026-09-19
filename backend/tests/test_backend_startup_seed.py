import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import init_db as real_init_db
from app.config import settings
from app.services.bot_settings_service import BotSettingsService


@pytest_asyncio.fixture
async def seed_session_maker(tmp_path):
    db_file = tmp_path / "startup_seed_test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)
    await real_init_db(db_engine=engine)
    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    yield session_maker
    await engine.dispose()


@pytest.mark.asyncio
async def test_lifespan_seeds_legacy_community_group_when_env_set(seed_session_maker, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(settings, "TELEGRAM_COMMUNITY_GROUP_ID", -100555)
    monkeypatch.setattr(main_module, "async_session_maker", seed_session_maker)
    monkeypatch.setattr(main_module, "init_db", AsyncMock())
    monkeypatch.setattr("app.services.telegram_relay.TelegramRelay.set_shared_client", lambda *a, **k: None)
    monkeypatch.setattr("app.services.ai_assistant.AIAssistantService.set_shared_client", lambda *a, **k: None)
    monkeypatch.setattr("app.services.crypto_service.CryptoService.set_shared_client", lambda *a, **k: None)

    async with main_module.lifespan(main_module.app):
        pass

    async with seed_session_maker() as session:
        value = await BotSettingsService.get_community_group_id(session)
    assert value == -100555


@pytest.mark.asyncio
async def test_lifespan_does_not_seed_when_env_unset(seed_session_maker, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(settings, "TELEGRAM_COMMUNITY_GROUP_ID", 0)
    monkeypatch.setattr(main_module, "async_session_maker", seed_session_maker)
    monkeypatch.setattr(main_module, "init_db", AsyncMock())
    monkeypatch.setattr("app.services.telegram_relay.TelegramRelay.set_shared_client", lambda *a, **k: None)
    monkeypatch.setattr("app.services.ai_assistant.AIAssistantService.set_shared_client", lambda *a, **k: None)
    monkeypatch.setattr("app.services.crypto_service.CryptoService.set_shared_client", lambda *a, **k: None)

    async with main_module.lifespan(main_module.app):
        pass

    async with seed_session_maker() as session:
        value = await BotSettingsService.get_community_group_id(session)
    assert value is None


@pytest.mark.asyncio
async def test_lifespan_never_overwrites_existing_persisted_value(seed_session_maker, monkeypatch):
    import app.main as main_module

    async with seed_session_maker() as session:
        await BotSettingsService.set_community_group_id(session, -100111, updated_by="owner")

    monkeypatch.setattr(settings, "TELEGRAM_COMMUNITY_GROUP_ID", -100999)
    monkeypatch.setattr(main_module, "async_session_maker", seed_session_maker)
    monkeypatch.setattr(main_module, "init_db", AsyncMock())
    monkeypatch.setattr("app.services.telegram_relay.TelegramRelay.set_shared_client", lambda *a, **k: None)
    monkeypatch.setattr("app.services.ai_assistant.AIAssistantService.set_shared_client", lambda *a, **k: None)
    monkeypatch.setattr("app.services.crypto_service.CryptoService.set_shared_client", lambda *a, **k: None)

    async with main_module.lifespan(main_module.app):
        pass

    async with seed_session_maker() as session:
        value = await BotSettingsService.get_community_group_id(session)
    assert value == -100111
