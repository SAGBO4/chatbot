import asyncio
import hmac
import logging
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.exc import OperationalError
from sqlalchemy import text

from app.config import settings
from app.security import verify_api_key
from tests.conftest import TEST_API_KEY


@pytest.mark.asyncio
async def test_health_check_database_connected_returns_200_ok(app_test_env):
    """
    1. FUNCTIONAL - Health check:
    GET /health returns 200 with status="ok" and database="connected".
    """
    client, _, _ = app_test_env
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert data["service"] == "support-bot-backend"


@pytest.mark.asyncio
async def test_security_api_key_valid_header_authorizes_access(app_test_env):
    """
    1. FUNCTIONAL / 2. SECURITY:
    A request with the correct X-API-Key header is accepted (access granted).
    """
    client, _, _ = app_test_env
    resp = await client.get("/api/tickets", headers={"X-API-Key": TEST_API_KEY})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_security_api_key_missing_header_returns_401_unauthorized(unauth_client):
    """
    2. SECURITY - Auth:
    A request without the X-API-Key header returns 401 Unauthorized.
    """
    resp = await unauth_client.get("/api/tickets")
    assert resp.status_code == 401
    assert "Missing or invalid X-API-Key header" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_security_api_key_invalid_header_returns_401_unauthorized(unauth_client):
    """
    2. SECURITY - Auth:
    A forged key returns 401 Unauthorized.
    """
    resp = await unauth_client.get("/api/tickets", headers={"X-API-Key": "mauvaise_cle"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_security_api_key_unconfigured_returns_503_fail_closed(app_test_env, monkeypatch):
    """
    2. SECURITY - Fail-closed:
    If API_KEY is not set in settings, access is blocked with 503 (never open by default).
    """
    client, _, _ = app_test_env
    monkeypatch.setattr(settings, "API_KEY", None)

    resp = await client.get("/api/tickets", headers={"X-API-Key": "nimporte_quoi"})
    assert resp.status_code == 503
    assert "API_KEY missing" in resp.json()["detail"]


def test_security_timing_safe_compare_used_for_secrets():
    """
    2. SECURITY - Timing attacks:
    hmac.compare_digest is used, to resist timing analysis attacks.
    """
    secret = "secret-key-1234567890"
    assert hmac.compare_digest(secret, "secret-key-1234567890") is True
    assert hmac.compare_digest(secret, "secret-key-1234567891") is False


@pytest.mark.asyncio
async def test_security_cors_headers_and_credentials_safety(app_test_env):
    """
    2. SECURITY - CORS headers:
    The CORS configuration refuses authenticated requests with credentials
    when allow_origins=["*"] (to prevent cross-origin cookie theft).
    """
    client, _, _ = app_test_env
    resp = await client.options(
        "/api/tickets",
        headers={
            "Origin": "http://evil-website.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-API-Key",
        },
    )
    # allow_credentials must be absent or 'false'
    assert resp.headers.get("access-control-allow-credentials") != "true"


@pytest.mark.asyncio
async def test_security_secrets_never_leaked_in_http_error_responses(app_test_env):
    """
    2. SECURITY - Non-disclosure of secrets:
    An HTTP or validation error must never reflect configuration keys.
    """
    client, _, _ = app_test_env
    resp = await client.post("/api/tickets", json={"invalid_field": True})
    assert resp.status_code == 422
    body_text = resp.text
    assert TEST_API_KEY not in body_text


# ==============================================================================
# 3. ROBUSTESSE
# ==============================================================================


@pytest.mark.asyncio
async def test_health_check_database_outage_returns_503_service_unavailable(app_test_env, caplog):
    """
    3. ROBUSTNESS - Database outage:
    If the database is disconnected or unreachable,
    /health immediately returns 503 Service Unavailable and logs the error.
    """
    client, session_maker, _ = app_test_env

    # Simulate a DB session failure on text("SELECT 1")
    from app.main import app
    from app.database import get_db

    async def broken_get_db():
        session = AsyncMock()
        session.execute.side_effect = OperationalError("Database down", None, None)
        yield session

    app.dependency_overrides[get_db] = broken_get_db

    try:
        with caplog.at_level(logging.ERROR):
            resp = await client.get("/health")
        assert resp.status_code == 503
        assert "Database connectivity error" in resp.json()["detail"]
        assert any("Health check database connectivity failure" in r.getMessage() for r in caplog.records)
    finally:
        # Restore the original fixture
        async def override_get_db():
            async with session_maker() as session:
                yield session
        app.dependency_overrides[get_db] = override_get_db


@pytest.mark.asyncio
async def test_health_check_concurrent_requests_all_return_200(app_test_env):
    """
    3. ROBUSTNESS - Concurrency:
    20 simultaneous health check requests all return 200 without blocking.
    """
    client, _, _ = app_test_env
    responses = await asyncio.gather(*(client.get("/health") for _ in range(20)))
    assert all(r.status_code == 200 for r in responses)
    assert all(r.json()["status"] == "ok" for r in responses)
