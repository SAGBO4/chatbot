"""API-written messages (query fallbacks, emails, email-resolution notices) follow the bot language."""
from unittest.mock import AsyncMock

import pytest

from app.models import KnowledgeArticle
from app.services.ai_assistant import AIAssistantService
from app.services.email_service import EmailService
from app.services.telegram_relay import TelegramRelay


async def set_language(client, lang):
    resp = await client.put("/api/admin/settings/language", json={"value": lang})
    assert resp.status_code == 200


async def create_ticket(client, user_id=4242):
    resp = await client.post(
        "/api/tickets",
        json={"user_id": user_id, "user_handle": "alice", "question": "How do I export?", "automated_answer": None},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "lang,empty,no_match",
    [
        (None, "Veuillez poser une question", "Je n'ai pas trouvé de réponse directe"),
        ("en", "Please ask a question", "I couldn't find a direct answer"),
    ],
)
async def test_query_fallback_messages_follow_the_bot_language(app_test_env, lang, empty, no_match):
    client, _, _ = app_test_env
    if lang:
        await set_language(client, lang)

    blank = await client.post("/api/query", json={"query": "   "})
    unknown = await client.post("/api/query", json={"query": "zzzz qqqq"})

    assert empty in blank.json()["answer"]
    assert no_match in unknown.json()["answer"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "lang,created_subject,resolved_subject,none_word",
    [
        (None, "Nouvelle demande de support de @alice", "Résolu via TELEGRAM", "Aucune"),
        ("en", "New support request from @alice", "Resolved via TELEGRAM", "None"),
    ],
)
async def test_support_team_emails_follow_the_bot_language(app_test_env, monkeypatch, lang, created_subject, resolved_subject, none_word):
    client, _, _ = app_test_env
    send = AsyncMock(return_value=True)
    monkeypatch.setattr(EmailService, "send_email_async", send)
    if lang:
        await set_language(client, lang)

    ticket_id = await create_ticket(client)
    created = send.call_args.kwargs
    assert f"[Ticket #{ticket_id}]" in created["subject"] and created_subject in created["subject"]
    assert f"#{ticket_id}" in created["body"] and none_word in created["body"]

    resp = await client.post(f"/api/tickets/{ticket_id}/resolve", json={"solution": "Use Settings."})
    assert resp.status_code == 200
    resolved = send.call_args.kwargs
    assert resolved_subject in resolved["subject"] and f"[Ticket #{ticket_id}]" in resolved["subject"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "lang,user_marker,group_marker",
    [
        (None, "Traité par", "résolu par Email"),
        ("en", "Handled by", "resolved by email"),
    ],
)
async def test_email_resolution_notices_follow_the_bot_language(app_test_env, monkeypatch, lang, user_marker, group_marker):
    from app.config import settings

    client, _, _ = app_test_env
    monkeypatch.setattr(EmailService, "send_email_async", AsyncMock(return_value=True))
    to_user, to_group = AsyncMock(return_value=True), AsyncMock(return_value=True)
    monkeypatch.setattr(TelegramRelay, "send_message_to_user", to_user)
    monkeypatch.setattr(TelegramRelay, "notify_support_group", to_group)
    if lang:
        await set_language(client, lang)
    ticket_id = await create_ticket(client)

    resp = await client.post(
        f"/api/webhooks/email-inbound/brevo?token={settings.BREVO_INBOUND_SECRET}",
        json={"items": [{"From": {"Address": "agent@company.com"}, "Subject": f"Re: [Ticket #{ticket_id}] help", "RawTextBody": "Use Settings."}]},
    )

    assert resp.json()["results"][0]["status"] == "resolved"
    assert user_marker in to_user.call_args[0][1]
    assert group_marker in to_group.call_args[0][0]


def test_ai_prompt_is_in_english_and_keeps_the_answer_language_rule():
    article = KnowledgeArticle(question="How to export?", solution="Open Settings, then Export.")
    extra = [(KnowledgeArticle(question=f"Extra {i}", solution=f"Solution {i}"), 0.5) for i in range(4)]

    prompt = AIAssistantService._build_prompt("Comment exporter ?", [(article, 0.9)] + extra)

    assert "You are a helpful, concise technical support assistant" in prompt
    assert "same language as the user's question" in prompt
    assert "Comment exporter ?" in prompt and "Open Settings, then Export." in prompt
    assert "Solution 0" in prompt and "Solution 1" in prompt, "the top 3 articles are used"
    assert "Solution 2" not in prompt, "the 4th article is left out"
    assert "Tu es" not in prompt
