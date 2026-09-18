import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import status
from httpx import AsyncClient, ASGITransport
from sqlalchemy.exc import OperationalError

from backend.main import app, lifespan
from backend.config import settings
from backend.database import get_db


@pytest.mark.asyncio
async def test_health_check_healthy():
    """Verify that /health returns HTTP 200 and 'connected' when DB is accessible."""
    mock_session = AsyncMock()
    mock_session.execute.return_value = None

    async def override_get_db():
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "ok"
            assert data["database"] == "connected"
            assert data["service"] == "support-bot-backend"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_health_check_database_unreachable():
    """Verify that /health returns HTTP 503 when the database fails ping."""
    mock_failing_session = AsyncMock()
    mock_failing_session.execute.side_effect = OperationalError("connection refused", {}, None)

    async def override_failing_get_db():
        yield mock_failing_session

    app.dependency_overrides[get_db] = override_failing_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert response.json()["detail"] == "Database connectivity error"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_sentry_initialization_bypass_when_unset():
    """Verify that Sentry is not initialized when SENTRY_DSN is None."""
    with patch.object(settings, "SENTRY_DSN", None):
        with patch.dict(sys.modules, {"sentry_sdk": MagicMock()}):
            import sentry_sdk
            sentry_sdk.init.reset_mock()

            # Execute backend lifespan
            test_app = MagicMock()
            async with lifespan(test_app):
                pass

            sentry_sdk.init.assert_not_called()


@pytest.mark.asyncio
async def test_sentry_initialization_when_dsn_provided():
    """Verify that Sentry is initialized when SENTRY_DSN is configured."""
    mock_sentry = MagicMock()
    with patch.object(settings, "SENTRY_DSN", "https://mockkey@sentry.io/123456"):
        with patch.dict(sys.modules, {"sentry_sdk": mock_sentry}):
            test_app = MagicMock()
            async with lifespan(test_app):
                pass

            mock_sentry.init.assert_called_once_with(
                dsn="https://mockkey@sentry.io/123456",
                traces_sample_rate=1.0,
            )


@pytest.mark.asyncio
async def test_sentry_graceful_handling_when_module_not_installed():
    """Verify that an ImportError for sentry_sdk does not crash startup."""
    with patch.object(settings, "SENTRY_DSN", "https://mockkey@sentry.io/123456"):
        with patch.dict(sys.modules, {"sentry_sdk": None}):
            test_app = MagicMock()
            # Must not raise an exception
            async with lifespan(test_app):
                pass
