import pytest
import pytest_asyncio
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.limiter import limiter
from backend.main import app
from backend.database import get_db, init_db
from backend.config import settings

TEST_API_KEY = "test-api-key-secret-12345"
TEST_EMAIL_WEBHOOK_SECRET = "test-email-webhook-secret-67890"
TEST_BREVO_INBOUND_SECRET = "test-brevo-inbound-secret-abcde"


@pytest.fixture(autouse=True)
def manage_rate_limiting_for_tests(request):
    """
    Ensures tests don't inadvertently fail due to rate limits when creating
    tickets or querying rapidly, while allowing rate limiting tests to test
    behavior explicitly.
    """
    path = request.node.fspath.strpath
    if "test_rate_limiting" in path or "ratelimit" in path:
        limiter.enabled = True
        if hasattr(limiter, "reset"):
            limiter.reset()
        yield
    else:
        prev = getattr(limiter, "enabled", True)
        limiter.enabled = False
        yield
        limiter.enabled = prev


@pytest.fixture(autouse=True)
def prevent_real_external_network_calls(request, monkeypatch):
    """
    Prevents background tasks from accidentally making real SMTP connections
    to external mail relays (like smtp-relay.brevo.com) or external AI/Telegram APIs
    during tests unless explicitly tested in a dedicated service test file.
    """
    path = request.node.fspath.strpath
    if "test_email_service" not in path and "test_feature_email_service" not in path:
        monkeypatch.setattr("backend.services.email_service.EmailService._send_smtp_sync", lambda msg: True)
    if "telegram_relay" not in path and "test_feature_telegram_relay" not in path:
        from unittest.mock import AsyncMock
        monkeypatch.setattr("backend.services.telegram_relay.TelegramRelay._send_telegram_message", AsyncMock(return_value=True))


@pytest_asyncio.fixture
async def app_test_env(tmp_path, monkeypatch):
    """
    Provides an isolated temporary SQLite database, configured test secrets,
    and an authenticated httpx.AsyncClient connected to the FastAPI app via ASGITransport.
    Yields (client, session_maker, engine).
    """
    monkeypatch.setattr(settings, "API_KEY", TEST_API_KEY)
    monkeypatch.setattr(settings, "EMAIL_WEBHOOK_SECRET", TEST_EMAIL_WEBHOOK_SECRET)
    monkeypatch.setattr(settings, "BREVO_INBOUND_SECRET", TEST_BREVO_INBOUND_SECRET)
    monkeypatch.setattr(settings, "AI_ENABLED", False)

    db_file = tmp_path / "app_test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)
    await init_db(db_engine=engine)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"X-API-Key": TEST_API_KEY},
    ) as client:
        yield client, session_maker, engine

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def unauth_client(monkeypatch):
    """Provides an unauthenticated httpx.AsyncClient (no X-API-Key)."""
    monkeypatch.setattr(settings, "API_KEY", TEST_API_KEY)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield client
