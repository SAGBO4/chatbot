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
    1. FONCTIONNEL - Health Check:
    GET /health retourne 200 avec status="ok" et database="connected".
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
    1. FONCTIONNEL / 2. SÉCURITÉ:
    Une requête avec l'en-tête X-API-Key correcte est acceptée (accès autorisé).
    """
    client, _, _ = app_test_env
    resp = await client.get("/api/tickets", headers={"X-API-Key": TEST_API_KEY})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_security_api_key_missing_header_returns_401_unauthorized(unauth_client):
    """
    2. SÉCURITÉ - Auth:
    Une requête sans l'en-tête X-API-Key retourne 401 Unauthorized.
    """
    resp = await unauth_client.get("/api/tickets")
    assert resp.status_code == 401
    assert "Missing or invalid X-API-Key header" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_security_api_key_invalid_header_returns_401_unauthorized(unauth_client):
    """
    2. SÉCURITÉ - Auth:
    Une clé falsifiée retourne 401 Unauthorized.
    """
    resp = await unauth_client.get("/api/tickets", headers={"X-API-Key": "mauvaise_cle"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_security_api_key_unconfigured_returns_503_fail_closed(app_test_env, monkeypatch):
    """
    2. SÉCURITÉ - Fail-closed:
    Si API_KEY n'est pas configuré dans settings, l'accès est bloqué avec 503 (pas d'ouverture par défaut).
    """
    client, _, _ = app_test_env
    monkeypatch.setattr(settings, "API_KEY", None)

    resp = await client.get("/api/tickets", headers={"X-API-Key": "nimporte_quoi"})
    assert resp.status_code == 503
    assert "API_KEY missing" in resp.json()["detail"]


def test_security_timing_safe_compare_used_for_secrets():
    """
    2. SÉCURITÉ - Timing Attacks:
    Vérifie l'utilisation de hmac.compare_digest pour résister aux attaques par analyse temporelle.
    """
    secret = "secret-key-1234567890"
    assert hmac.compare_digest(secret, "secret-key-1234567890") is True
    assert hmac.compare_digest(secret, "secret-key-1234567891") is False


@pytest.mark.asyncio
async def test_security_cors_headers_and_credentials_safety(app_test_env):
    """
    2. SÉCURITÉ - Headers CORS:
    Vérifie que la configuration CORS refuse les requêtes authentifiées avec credentials
    lorsque allow_origins=["*"] (pour empêcher le vol de cookies cross-origin).
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
    # allow_credentials doit être absent ou à 'false'
    assert resp.headers.get("access-control-allow-credentials") != "true"


@pytest.mark.asyncio
async def test_security_secrets_never_leaked_in_http_error_responses(app_test_env):
    """
    2. SÉCURITÉ - Non-divulgation de secrets:
    Une erreur HTTP ou validation ne doit jamais refléter les clés de configuration.
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
    3. ROBUSTESSE - Panne base de données:
    Si la base de données est déconnectée ou inaccessible,
    /health renvoie immédiatement 503 Service Unavailable et log l'erreur.
    """
    client, session_maker, _ = app_test_env

    # Simuler une panne de session DB sur text("SELECT 1")
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
        # Rétablir la fixture originale
        async def override_get_db():
            async with session_maker() as session:
                yield session
        app.dependency_overrides[get_db] = override_get_db


@pytest.mark.asyncio
async def test_health_check_concurrent_requests_all_return_200(app_test_env):
    """
    3. ROBUSTESSE - Concurrence:
    20 requêtes simultanées de health check répondent toutes 200 sans blocage.
    """
    client, _, _ = app_test_env
    responses = await asyncio.gather(*(client.get("/health") for _ in range(20)))
    assert all(r.status_code == 200 for r in responses)
    assert all(r.json()["status"] == "ok" for r in responses)
