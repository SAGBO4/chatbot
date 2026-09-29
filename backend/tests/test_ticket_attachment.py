"""
The web portal's ticket-attachment upload: decoding a data: URL, and forwarding it straight to the
support group over Telegram, with nothing written to disk and nothing persisted on the ticket.

Replaces the frontend's old `POST /api/attachments`, which wrote to the Next.js server's local
filesystem (unusable on a serverless host: the filesystem is read-only at request time) and had no
authentication at all.
"""
import base64

import pytest

from app.attachments import InvalidAttachment, decode_data_url, extension_for

# A minimal valid 1x1 PNG, small enough to keep the test fast.
_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
_PNG_DATA_URL = f"data:image/png;base64,{_PNG_BASE64}"


# ---------------------------------------------------------------------------
# app.attachments.decode_data_url
# ---------------------------------------------------------------------------


class TestDecodeDataUrl:
    def test_valid_png_decodes(self):
        decoded = decode_data_url(_PNG_DATA_URL)
        assert decoded.mime_type == "image/png"
        assert decoded.content == base64.b64decode(_PNG_BASE64)

    def test_not_a_data_url_is_rejected(self):
        with pytest.raises(InvalidAttachment):
            decode_data_url("https://example.com/image.png")

    def test_missing_base64_marker_is_rejected(self):
        with pytest.raises(InvalidAttachment):
            decode_data_url(f"data:image/png,{_PNG_BASE64}")

    def test_disallowed_mime_type_is_rejected(self):
        svg = base64.b64encode(b"<svg onload=alert(1)></svg>").decode()
        with pytest.raises(InvalidAttachment, match="Unsupported image type"):
            decode_data_url(f"data:image/svg+xml;base64,{svg}")

    def test_html_mime_type_is_rejected(self):
        """Nothing that could be rendered as a page or script gets through, only the four image types."""
        payload = base64.b64encode(b"<script>alert(1)</script>").decode()
        with pytest.raises(InvalidAttachment):
            decode_data_url(f"data:text/html;base64,{payload}")

    def test_invalid_base64_is_rejected(self):
        with pytest.raises(InvalidAttachment, match="Invalid base64"):
            decode_data_url("data:image/png;base64,not-valid-base64!!!")

    def test_empty_content_is_rejected(self):
        with pytest.raises(InvalidAttachment, match="Empty"):
            decode_data_url("data:image/png;base64,")

    def test_oversized_content_is_rejected_on_decoded_size_not_declared_size(self):
        """The limit is enforced on what's actually decoded - a caller cannot lie about the size."""
        big = base64.b64encode(b"a" * (5 * 1024 * 1024 + 1)).decode()
        with pytest.raises(InvalidAttachment, match="exceeds"):
            decode_data_url(f"data:image/jpeg;base64,{big}")

    def test_exactly_at_the_limit_is_accepted(self):
        at_limit = base64.b64encode(b"a" * (5 * 1024 * 1024)).decode()
        decoded = decode_data_url(f"data:image/jpeg;base64,{at_limit}")
        assert len(decoded.content) == 5 * 1024 * 1024

    def test_mime_type_is_case_insensitive(self):
        decoded = decode_data_url(f"data:IMAGE/PNG;base64,{_PNG_BASE64}")
        assert decoded.mime_type == "image/png"

    @pytest.mark.parametrize("mime", ["image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"])
    def test_every_documented_type_is_accepted(self, mime):
        decoded = decode_data_url(f"data:{mime};base64,{_PNG_BASE64}")
        assert decoded.mime_type == mime


class TestExtensionFor:
    def test_known_types_map_to_their_extension(self):
        assert extension_for("image/png") == "png"
        assert extension_for("image/jpeg") == "jpg"
        assert extension_for("image/webp") == "webp"
        assert extension_for("image/gif") == "gif"

    def test_unknown_type_falls_back_to_png(self):
        assert extension_for("image/bmp") == "png"


# ---------------------------------------------------------------------------
# POST /api/tickets/{id}/attachment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_attach_photo_forwards_to_support_group(app_test_env, monkeypatch):
    from app.services.telegram_relay import TelegramRelay

    client, session_maker, _ = app_test_env
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)
    monkeypatch.setattr("app.config.settings.TELEGRAM_BOT_TOKEN", "123:real-token")

    sent = {}

    async def fake_send_photo(content, mime_type, filename, caption):
        sent["content"] = content
        sent["mime_type"] = mime_type
        sent["filename"] = filename
        sent["caption"] = caption
        return True

    monkeypatch.setattr(TelegramRelay, "send_photo_to_support_group", fake_send_photo)

    created = await client.post(
        "/api/tickets", json={"user_id": 42, "user_handle": "alice", "question": "help"}
    )
    ticket_id = created.json()["id"]

    response = await client.post(
        f"/api/tickets/{ticket_id}/attachment", json={"data_url": _PNG_DATA_URL}
    )

    assert response.status_code == 200
    assert response.json() == {"forwarded": True}
    assert sent["mime_type"] == "image/png"
    assert sent["content"] == base64.b64decode(_PNG_BASE64)
    assert str(ticket_id) in sent["caption"]
    assert "alice" in sent["caption"]


@pytest.mark.asyncio
async def test_attach_photo_unknown_ticket_returns_404(app_test_env):
    client, _, _ = app_test_env
    response = await client.post(
        "/api/tickets/999999/attachment", json={"data_url": _PNG_DATA_URL}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_attach_photo_rejects_disallowed_type_without_calling_telegram(app_test_env, monkeypatch):
    from app.services.telegram_relay import TelegramRelay

    client, _, _ = app_test_env
    relay_called = False

    async def fake_send_photo(*args, **kwargs):
        nonlocal relay_called
        relay_called = True
        return True

    monkeypatch.setattr(TelegramRelay, "send_photo_to_support_group", fake_send_photo)

    created = await client.post("/api/tickets", json={"user_id": 1, "question": "help"})
    ticket_id = created.json()["id"]

    svg = base64.b64encode(b"<svg></svg>").decode()
    response = await client.post(
        f"/api/tickets/{ticket_id}/attachment", json={"data_url": f"data:image/svg+xml;base64,{svg}"}
    )

    assert response.status_code == 400
    assert not relay_called


@pytest.mark.asyncio
async def test_attach_photo_requires_the_api_key(app_test_env, unauth_client):
    client, _, _ = app_test_env
    created = await client.post("/api/tickets", json={"user_id": 1, "question": "help"})
    ticket_id = created.json()["id"]

    response = await unauth_client.post(
        f"/api/tickets/{ticket_id}/attachment", json={"data_url": _PNG_DATA_URL}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_attach_photo_nothing_is_persisted_on_the_ticket(app_test_env, monkeypatch):
    """The attachment is forwarded, never stored: the ticket record itself must stay unchanged."""
    from app.services.telegram_relay import TelegramRelay

    async def fake_send_photo(*args, **kwargs):
        return True

    client, session_maker, _ = app_test_env
    monkeypatch.setattr(TelegramRelay, "send_photo_to_support_group", fake_send_photo)

    created = await client.post("/api/tickets", json={"user_id": 1, "question": "help"})
    ticket_id = created.json()["id"]
    before = (await client.get(f"/api/tickets/{ticket_id}")).json()

    await client.post(f"/api/tickets/{ticket_id}/attachment", json={"data_url": _PNG_DATA_URL})

    after = (await client.get(f"/api/tickets/{ticket_id}")).json()
    assert before == after


@pytest.mark.asyncio
async def test_attach_photo_failed_relay_is_reported_but_not_an_error(app_test_env, monkeypatch):
    """Telegram rejecting the photo is a normal, reportable outcome - not a 500."""
    from app.services.telegram_relay import TelegramRelay

    client, _, _ = app_test_env

    async def fake_send_photo(*args, **kwargs):
        return False

    monkeypatch.setattr(TelegramRelay, "send_photo_to_support_group", fake_send_photo)

    created = await client.post("/api/tickets", json={"user_id": 1, "question": "help"})
    ticket_id = created.json()["id"]

    response = await client.post(
        f"/api/tickets/{ticket_id}/attachment", json={"data_url": _PNG_DATA_URL}
    )
    assert response.status_code == 200
    assert response.json() == {"forwarded": False}


# ---------------------------------------------------------------------------
# TelegramRelay.send_photo_to_support_group
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_photo_posts_multipart_to_the_telegram_api(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    from app.services.telegram_relay import TelegramRelay

    monkeypatch.setattr("app.config.settings.TELEGRAM_BOT_TOKEN", "123:real-token")
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    mock_client = AsyncMock()
    mock_client.is_closed = False
    mock_client.post.return_value = MagicMock(status_code=200)
    TelegramRelay.set_shared_client(mock_client)
    try:
        ok = await TelegramRelay.send_photo_to_support_group(
            content=b"fake-bytes", mime_type="image/png", filename="ticket-1.png", caption="hello"
        )
    finally:
        TelegramRelay.set_shared_client(None)

    assert ok is True
    call = mock_client.post.call_args
    assert call.args[0].endswith("/sendPhoto")
    assert call.kwargs["data"]["chat_id"] == -100999888
    assert call.kwargs["files"]["photo"] == ("ticket-1.png", b"fake-bytes", "image/png")


@pytest.mark.asyncio
async def test_send_photo_simulated_when_token_unset(monkeypatch):
    from app.services.telegram_relay import TelegramRelay

    monkeypatch.setattr("app.config.settings.TELEGRAM_BOT_TOKEN", "placeholder_token")
    ok = await TelegramRelay.send_photo_to_support_group(
        content=b"x", mime_type="image/png", filename="a.png", caption="c"
    )
    assert ok is True


@pytest.mark.asyncio
async def test_send_photo_simulated_when_support_group_unset(monkeypatch):
    from app.services.telegram_relay import TelegramRelay

    monkeypatch.setattr("app.config.settings.TELEGRAM_BOT_TOKEN", "123:real-token")
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", 0)
    ok = await TelegramRelay.send_photo_to_support_group(
        content=b"x", mime_type="image/png", filename="a.png", caption="c"
    )
    assert ok is True


@pytest.mark.asyncio
async def test_send_photo_returns_false_on_telegram_error_status(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock

    from app.services.telegram_relay import TelegramRelay

    monkeypatch.setattr("app.config.settings.TELEGRAM_BOT_TOKEN", "123:real-token")
    monkeypatch.setattr("app.config.settings.TELEGRAM_SUPPORT_GROUP_ID", -100999888)

    mock_client = AsyncMock()
    mock_client.is_closed = False
    mock_client.post.return_value = MagicMock(status_code=400, text="Bad Request: PHOTO_INVALID_DIMENSIONS")
    TelegramRelay.set_shared_client(mock_client)
    try:
        ok = await TelegramRelay.send_photo_to_support_group(
            content=b"x", mime_type="image/png", filename="a.png", caption="c"
        )
    finally:
        TelegramRelay.set_shared_client(None)
    assert ok is False
