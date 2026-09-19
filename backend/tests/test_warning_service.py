import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import init_db
from app.services.warning_service import WarningService


@pytest_asyncio.fixture
async def async_session(tmp_path):
    db_file = tmp_path / "warnings_test.db"
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)
    await init_db(db_engine=test_engine)

    session_maker = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_maker() as session:
        yield session

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_add_warning_persists_fields(async_session):
    warning = await WarningService.add_warning(
        session=async_session,
        user_id=111,
        group_id=-100222,
        warned_by="admin_alice",
        reason="Spam links",
    )
    assert warning.id is not None
    assert warning.user_id == 111
    assert warning.group_id == -100222
    assert warning.warned_by == "admin_alice"
    assert warning.reason == "Spam links"


@pytest.mark.asyncio
async def test_count_and_list_warnings_scoped_per_user_and_group(async_session):
    await WarningService.add_warning(async_session, user_id=1, group_id=-100, warned_by="a", reason="r1")
    await WarningService.add_warning(async_session, user_id=1, group_id=-100, warned_by="b", reason="r2")
    # Different group should not count toward the same user's total in group -100
    await WarningService.add_warning(async_session, user_id=1, group_id=-200, warned_by="a", reason="r3")
    # Different user in the same group should not be counted either
    await WarningService.add_warning(async_session, user_id=2, group_id=-100, warned_by="a", reason="r4")

    warnings = await WarningService.list_warnings(async_session, user_id=1, group_id=-100)
    assert len(warnings) == 2
    assert {w.reason for w in warnings} == {"r1", "r2"}
    # Most recent first
    assert warnings[0].reason == "r2"


@pytest.mark.asyncio
async def test_add_warning_without_reason(async_session):
    warning = await WarningService.add_warning(
        session=async_session, user_id=5, group_id=-500, warned_by="admin_bob"
    )
    assert warning.reason is None
