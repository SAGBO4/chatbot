import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import init_db
from app.services.bot_settings_service import BotSettingsService, WhitelistService, DEFAULT_LANGUAGE


@pytest_asyncio.fixture
async def async_session(tmp_path):
    db_file = tmp_path / "bot_settings_test.db"
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)
    await init_db(db_engine=test_engine)

    session_maker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_get_value_returns_none_when_unset(async_session):
    assert await BotSettingsService.get_value(async_session, "missing_key") is None


@pytest.mark.asyncio
async def test_set_then_get_value(async_session):
    await BotSettingsService.set_value(async_session, "some_key", "some_value", updated_by="tester")
    assert await BotSettingsService.get_value(async_session, "some_key") == "some_value"


@pytest.mark.asyncio
async def test_set_value_overwrites_existing(async_session):
    await BotSettingsService.set_value(async_session, "k", "v1")
    await BotSettingsService.set_value(async_session, "k", "v2")
    assert await BotSettingsService.get_value(async_session, "k") == "v2"


@pytest.mark.asyncio
async def test_community_group_id_get_set(async_session):
    assert await BotSettingsService.get_community_group_id(async_session) is None
    await BotSettingsService.set_community_group_id(async_session, -100555, updated_by="owner")
    assert await BotSettingsService.get_community_group_id(async_session) == -100555


@pytest.mark.asyncio
async def test_language_defaults_to_french(async_session):
    assert await BotSettingsService.get_language(async_session) == DEFAULT_LANGUAGE


@pytest.mark.asyncio
async def test_language_set_and_get(async_session):
    await BotSettingsService.set_language(async_session, "en", updated_by="owner")
    assert await BotSettingsService.get_language(async_session) == "en"


@pytest.mark.asyncio
async def test_seed_legacy_community_group_seeds_when_absent(async_session):
    seeded = await BotSettingsService.seed_legacy_community_group(async_session, -100999)
    assert seeded is True
    assert await BotSettingsService.get_community_group_id(async_session) == -100999


@pytest.mark.asyncio
async def test_seed_legacy_community_group_never_overwrites(async_session):
    await BotSettingsService.set_community_group_id(async_session, -100111, updated_by="owner")
    seeded = await BotSettingsService.seed_legacy_community_group(async_session, -100999)
    assert seeded is False
    assert await BotSettingsService.get_community_group_id(async_session) == -100111


@pytest.mark.asyncio
async def test_whitelist_add_and_is_whitelisted(async_session):
    assert await WhitelistService.is_whitelisted(async_session, 42) is False
    await WhitelistService.add(async_session, 42, added_by="owner")
    assert await WhitelistService.is_whitelisted(async_session, 42) is True


@pytest.mark.asyncio
async def test_whitelist_add_idempotent(async_session):
    entry1 = await WhitelistService.add(async_session, 42, added_by="owner")
    entry2 = await WhitelistService.add(async_session, 42, added_by="owner_again")
    assert entry1.user_id == entry2.user_id == 42
    entries = await WhitelistService.list_entries(async_session)
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_whitelist_remove(async_session):
    await WhitelistService.add(async_session, 42, added_by="owner")
    removed = await WhitelistService.remove(async_session, 42)
    assert removed is True
    assert await WhitelistService.is_whitelisted(async_session, 42) is False


@pytest.mark.asyncio
async def test_whitelist_remove_nonexistent_returns_false(async_session):
    removed = await WhitelistService.remove(async_session, 999)
    assert removed is False


@pytest.mark.asyncio
async def test_whitelist_list_order(async_session):
    await WhitelistService.add(async_session, 1, added_by="owner")
    await WhitelistService.add(async_session, 2, added_by="owner")
    entries = await WhitelistService.list_entries(async_session)
    assert [e.user_id for e in entries] == [1, 2]
