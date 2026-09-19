"""Every route must demand the API key, except the few that authenticate another way or are public."""
import pytest

from app.main import app

# Public liveness probe, and the two inbound-email webhooks that check their own secret
OWN_AUTH = {("POST", "/api/webhooks/email-inbound"), ("POST", "/api/webhooks/email-inbound/brevo")}
PUBLIC = {("GET", "/health")}


def _operations():
    for path, item in app.openapi()["paths"].items():
        for method in item:
            yield method.upper(), path


def _concrete(path):
    """Fill the path parameters with plausible values."""
    for name, value in {"symbol": "btc", "key": "language", "message_id": "1", "ticket_id": "1", "user_id": "1"}.items():
        path = path.replace("{" + name + "}", value)
    assert "{" not in path, f"unknown path parameter in {path}"
    return path


def test_the_route_inventory_is_what_this_test_expects():
    operations = set(_operations())
    assert PUBLIC <= operations and OWN_AUTH <= operations, "a public route was renamed: update this test"
    assert len(operations - PUBLIC - OWN_AUTH) >= 15, "the list of protected routes looks truncated"


@pytest.mark.asyncio
async def test_every_other_route_refuses_a_request_without_the_api_key(unauth_client):
    unprotected = []
    for method, path in sorted(_operations()):
        if (method, path) in PUBLIC | OWN_AUTH:
            continue
        response = await unauth_client.request(method, _concrete(path), json={})
        if response.status_code != 401:
            unprotected.append(f"{method} {path} -> {response.status_code}")
    assert unprotected == []


@pytest.mark.asyncio
async def test_the_webhooks_refuse_requests_that_lack_their_own_secret(unauth_client):
    for method, path in sorted(OWN_AUTH):
        response = await unauth_client.request(method, path, json={})
        assert response.status_code in (401, 503), f"{method} {path} answered {response.status_code}"
