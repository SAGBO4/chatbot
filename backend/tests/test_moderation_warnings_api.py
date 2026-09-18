import pytest


@pytest.mark.asyncio
async def test_create_warning_returns_201_with_fields(app_test_env):
    client, _, _ = app_test_env
    resp = await client.post(
        "/api/moderation/warnings",
        json={"user_id": 42, "group_id": -100555, "warned_by": "admin_x", "reason": "spam"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["user_id"] == 42
    assert data["group_id"] == -100555
    assert data["warned_by"] == "admin_x"
    assert data["reason"] == "spam"
    assert "id" in data and "created_at" in data


@pytest.mark.asyncio
async def test_list_warnings_scoped_by_user_and_group(app_test_env):
    client, _, _ = app_test_env
    await client.post(
        "/api/moderation/warnings",
        json={"user_id": 1, "group_id": -100, "warned_by": "a", "reason": "r1"},
    )
    await client.post(
        "/api/moderation/warnings",
        json={"user_id": 1, "group_id": -100, "warned_by": "b", "reason": "r2"},
    )
    await client.post(
        "/api/moderation/warnings",
        json={"user_id": 1, "group_id": -200, "warned_by": "a", "reason": "other group"},
    )

    resp = await client.get("/api/moderation/warnings", params={"user_id": 1, "group_id": -100})
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    assert len(data["warnings"]) == 2


@pytest.mark.asyncio
async def test_create_warning_requires_api_key(unauth_client):
    resp = await unauth_client.post(
        "/api/moderation/warnings",
        json={"user_id": 1, "group_id": -100, "warned_by": "a"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_warnings_requires_api_key(unauth_client):
    resp = await unauth_client.get(
        "/api/moderation/warnings", params={"user_id": 1, "group_id": -100}
    )
    assert resp.status_code == 401
