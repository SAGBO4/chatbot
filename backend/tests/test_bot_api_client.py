import pytest
import httpx
from unittest.mock import AsyncMock, patch

from app.config import settings
from bot.api_client import BackendClient


@pytest.mark.asyncio
async def test_api_client_headers_includes_api_key_when_configured(monkeypatch):
    """
    1. FUNCTIONAL & SECURITY:
    BackendClient includes the X-API-Key header when API_KEY is configured.
    """
    monkeypatch.setattr(settings, "API_KEY", "secret-test-key")
    client = BackendClient(base_url="http://localhost:8000")
    headers = client._headers()
    assert headers == {"X-API-Key": "secret-test-key"}


@pytest.mark.asyncio
async def test_api_client_headers_empty_when_api_key_unset(monkeypatch):
    """
    1. FUNCTIONAL & SECURITY:
    BackendClient returns empty headers when API_KEY is None.
    """
    monkeypatch.setattr(settings, "API_KEY", None)
    client = BackendClient(base_url="http://localhost:8000")
    headers = client._headers()
    assert headers == {}


@pytest.mark.asyncio
async def test_api_client_lifecycle_close_closes_owned_session():
    """
    1. FUNCTIONAL:
    The httpx session is closed when the client owns it.
    """
    client = BackendClient(base_url="http://localhost:8000")
    internal_client = await client._get_client()
    assert internal_client.is_closed is False
    await client.close()
    assert internal_client.is_closed is True


@pytest.mark.asyncio
async def test_api_client_query_calls_correct_endpoint():
    """
    1. FUNCTIONAL:
    BackendClient.query calls POST /api/query with the right payload.
    """
    req = httpx.Request("POST", "http://test/api/query")
    mock_resp = httpx.Response(status_code=200, json={"found": True, "answer": "OK"}, request=req)
    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_http.is_closed = False
    mock_http.post.return_value = mock_resp

    client = BackendClient(base_url="http://test", client=mock_http)
    res = await client.query("Ma question", user_id=10, user_handle="jean")

    assert res == {"found": True, "answer": "OK"}
    mock_http.post.assert_called_once()
    assert mock_http.post.call_args[0][0] == "http://test/api/query"
    assert mock_http.post.call_args[1]["json"] == {
        "query": "Ma question",
        "user_id": 10,
        "user_handle": "jean",
    }


@pytest.mark.asyncio
async def test_api_client_create_ticket_calls_correct_endpoint():
    """
    1. FONCTIONNEL:
    BackendClient.create_ticket appelle POST /api/tickets.
    """
    req = httpx.Request("POST", "http://test/api/tickets")
    mock_resp = httpx.Response(status_code=201, json={"id": 99, "status": "OPEN"}, request=req)
    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_http.is_closed = False
    mock_http.post.return_value = mock_resp

    client = BackendClient(base_url="http://test", client=mock_http)
    res = await client.create_ticket(user_id=10, user_handle="jean", question="Panne", automated_answer="Ans")

    assert res["id"] == 99
    assert mock_http.post.call_args[0][0] == "http://test/api/tickets"


@pytest.mark.asyncio
async def test_api_client_resolve_ticket_calls_correct_endpoint():
    """
    1. FONCTIONNEL:
    BackendClient.resolve_ticket appelle POST /api/tickets/{id}/resolve.
    """
    req = httpx.Request("POST", "http://test/api/tickets/99/resolve")
    mock_resp = httpx.Response(status_code=200, json={"id": 99, "status": "RESOLVED"}, request=req)
    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_http.is_closed = False
    mock_http.post.return_value = mock_resp

    client = BackendClient(base_url="http://test", client=mock_http)
    res = await client.resolve_ticket(ticket_id=99, solution="Sol", resolved_by="agent")

    assert res["status"] == "RESOLVED"
    assert mock_http.post.call_args[0][0] == "http://test/api/tickets/99/resolve"


@pytest.mark.asyncio
async def test_api_client_attach_support_card_calls_correct_endpoint():
    """
    1. FONCTIONNEL:
    BackendClient.attach_support_card appelle POST /api/tickets/{id}/support-card.
    """
    req = httpx.Request("POST", "http://test/api/tickets/99/support-card")
    mock_resp = httpx.Response(status_code=200, json={"id": 99, "support_group_message_id": 123}, request=req)
    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_http.is_closed = False
    mock_http.post.return_value = mock_resp

    client = BackendClient(base_url="http://test", client=mock_http)
    res = await client.attach_support_card(ticket_id=99, message_id=123)

    assert res["support_group_message_id"] == 123
    assert mock_http.post.call_args[0][0] == "http://test/api/tickets/99/support-card"


@pytest.mark.asyncio
async def test_api_client_get_ticket_by_support_message_returns_none_on_404():
    """
    1. FUNCTIONAL:
    get_ticket_by_support_message returns None on an HTTP 404 (no exception raised).
    """
    req = httpx.Request("GET", "http://test/api/tickets/by-support-message/999")
    mock_resp = httpx.Response(status_code=404, json={"detail": "Not found"}, request=req)
    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_http.is_closed = False
    mock_http.get.return_value = mock_resp

    client = BackendClient(base_url="http://test", client=mock_http)
    res = await client.get_ticket_by_support_message(999)
    assert res is None


@pytest.mark.asyncio
async def test_api_client_get_ticket_by_support_message_returns_ticket_on_200():
    """
    1. FUNCTIONAL:
    get_ticket_by_support_message returns the ticket dictionary when found (HTTP 200).
    """
    req = httpx.Request("GET", "http://test/api/tickets/by-support-message/888")
    mock_resp = httpx.Response(status_code=200, json={"id": 77, "status": "OPEN"}, request=req)
    mock_http = AsyncMock(spec=httpx.AsyncClient)
    mock_http.is_closed = False
    mock_http.get.return_value = mock_resp

    client = BackendClient(base_url="http://test", client=mock_http)
    res = await client.get_ticket_by_support_message(888)
    assert res == {"id": 77, "status": "OPEN"}
