import pytest


@pytest.mark.asyncio
async def test_get_unset_setting_returns_null_value(app_test_env):
    client, _, _ = app_test_env
    resp = await client.get("/api/admin/settings/community_group_id")
    assert resp.status_code == 200
    data = resp.json()
    assert data["key"] == "community_group_id"
    assert data["value"] is None


@pytest.mark.asyncio
async def test_set_then_get_setting(app_test_env):
    client, _, _ = app_test_env
    put_resp = await client.put(
        "/api/admin/settings/community_group_id",
        json={"value": "-100555", "updated_by": "owner"},
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["value"] == "-100555"

    get_resp = await client.get("/api/admin/settings/community_group_id")
    assert get_resp.json()["value"] == "-100555"


@pytest.mark.asyncio
async def test_setting_endpoints_require_api_key(unauth_client):
    resp = await unauth_client.get("/api/admin/settings/community_group_id")
    assert resp.status_code == 401
    resp2 = await unauth_client.put("/api/admin/settings/community_group_id", json={"value": "1"})
    assert resp2.status_code == 401


@pytest.mark.asyncio
async def test_whitelist_add_list_check_remove(app_test_env):
    client, _, _ = app_test_env

    add_resp = await client.post("/api/admin/whitelist", json={"user_id": 42, "added_by": "owner"})
    assert add_resp.status_code == 201
    assert add_resp.json()["user_id"] == 42

    list_resp = await client.get("/api/admin/whitelist")
    assert list_resp.status_code == 200
    assert len(list_resp.json()["entries"]) == 1

    check_resp = await client.get("/api/admin/whitelist/42/check")
    assert check_resp.status_code == 200
    assert check_resp.json()["is_whitelisted"] is True

    check_missing = await client.get("/api/admin/whitelist/999/check")
    assert check_missing.json()["is_whitelisted"] is False

    remove_resp = await client.delete("/api/admin/whitelist/42")
    assert remove_resp.status_code == 200
    assert remove_resp.json()["removed"] is True

    check_after_remove = await client.get("/api/admin/whitelist/42/check")
    assert check_after_remove.json()["is_whitelisted"] is False


@pytest.mark.asyncio
async def test_remove_nonexistent_whitelist_entry_returns_404(app_test_env):
    client, _, _ = app_test_env
    resp = await client.delete("/api/admin/whitelist/12345")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_whitelist_endpoints_require_api_key(unauth_client):
    resp = await unauth_client.post("/api/admin/whitelist", json={"user_id": 1, "added_by": "x"})
    assert resp.status_code == 401
    resp2 = await unauth_client.get("/api/admin/whitelist")
    assert resp2.status_code == 401
    resp3 = await unauth_client.get("/api/admin/whitelist/1/check")
    assert resp3.status_code == 401
    resp4 = await unauth_client.delete("/api/admin/whitelist/1")
    assert resp4.status_code == 401
