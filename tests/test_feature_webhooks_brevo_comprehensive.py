import asyncio
import logging
import pytest
from unittest.mock import patch
from sqlalchemy import select

from backend.config import settings
from backend.models import Ticket, TicketStatus
from backend.services.ticket_service import TicketService
from tests.conftest import TEST_BREVO_INBOUND_SECRET


@pytest.mark.asyncio
async def test_webhooks_brevo_happy_path_single_item_resolves_ticket(app_test_env, caplog):
    """
    1. FONCTIONNEL - Happy Path:
    Vérifie qu'un webhook Brevo avec token valide et un élément dans items[]
    résout le ticket associé et retourne status="resolved".
    """
    client, session_maker, _ = app_test_env

    async with session_maker() as session:
        ticket = await TicketService.create_ticket(session, 100, "user1", "Question Brevo")
        t_id = ticket.id

    payload = {
        "items": [
            {
                "From": {"Address": "support@mycompany.com"},
                "Subject": f"Re: [Ticket #{t_id}] Réponse",
                "RawTextBody": "Texte brut de fallback",
                "ExtractedMarkdownMessage": "Solution markdown propre et directe.",
            }
        ]
    }

    with caplog.at_level(logging.INFO):
        response = await client.post(
            f"/api/webhooks/email-inbound/brevo?token={TEST_BREVO_INBOUND_SECRET}",
            json=payload,
        )

    # 4. ASSERTIONS
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 1
    item_res = data["results"][0]
    assert item_res["status"] == "resolved"
    assert item_res["ticket_id"] == t_id
    assert item_res["channel"] == "EMAIL"

    # Vérification DB
    async with session_maker() as session:
        t = (await session.execute(select(Ticket).where(Ticket.id == t_id))).scalar_one()
        assert t.status == "RESOLVED"
        assert t.solution == "Solution markdown propre et directe."
        assert t.resolved_by == "support@mycompany.com"


@pytest.mark.asyncio
async def test_webhooks_brevo_happy_path_batch_multiple_items_resolves_all(app_test_env):
    """
    1. FONCTIONNEL - Batching:
    Vérifie la résolution de plusieurs tickets différents dans un même lot Brevo.
    """
    client, session_maker, _ = app_test_env

    async with session_maker() as session:
        t1 = await TicketService.create_ticket(session, 1, "u1", "Q1")
        t2 = await TicketService.create_ticket(session, 2, "u2", "Q2")
        t3 = await TicketService.create_ticket(session, 3, "u3", "Q3")

    payload = {
        "items": [
            {
                "From": {"Address": "agent1@example.com"},
                "Subject": f"[Ticket #{t1.id}] Sol 1",
                "ExtractedMarkdownMessage": "Solution pour ticket 1",
            },
            {
                "From": {"Address": "agent2@example.com"},
                "Subject": f"[Ticket #{t2.id}] Sol 2",
                "ExtractedMarkdownMessage": "Solution pour ticket 2",
            },
            {
                "From": {"Address": "agent3@example.com"},
                "Subject": f"[Ticket #{t3.id}] Sol 3",
                "ExtractedMarkdownMessage": "Solution pour ticket 3",
            },
        ]
    }

    response = await client.post(
        f"/api/webhooks/email-inbound/brevo?token={TEST_BREVO_INBOUND_SECRET}",
        json=payload,
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 3
    assert all(r["status"] == "resolved" for r in results)

    # Vérification DB
    async with session_maker() as session:
        tickets = (await session.execute(select(Ticket).where(Ticket.id.in_([t1.id, t2.id, t3.id])))).scalars().all()
        assert all(t.status == "RESOLVED" for t in tickets)


@pytest.mark.asyncio
async def test_webhooks_brevo_prefers_extracted_markdown_over_raw_text(app_test_env):
    """
    1. FONCTIONNEL - Sélection du meilleur corps:
    Brevo fournit à la fois ExtractedMarkdownMessage et RawTextBody;
    l'orchestrateur doit privilégier ExtractedMarkdownMessage.
    """
    client, session_maker, _ = app_test_env

    async with session_maker() as session:
        t = await TicketService.create_ticket(session, 1, "u", "Q")
        t_id = t.id

    payload = {
        "items": [
            {
                "From": {"Address": "agent@example.com"},
                "Subject": f"[Ticket #{t_id}]",
                "RawTextBody": "Raw text fallback",
                "ExtractedMarkdownMessage": "Markdown prioritaire",
            }
        ]
    }

    resp = await client.post(
        f"/api/webhooks/email-inbound/brevo?token={TEST_BREVO_INBOUND_SECRET}",
        json=payload,
    )
    assert resp.status_code == 200

    async with session_maker() as session:
        refreshed = (await session.execute(select(Ticket).where(Ticket.id == t_id))).scalar_one()
        assert refreshed.solution == "Markdown prioritaire"


@pytest.mark.asyncio
async def test_webhooks_brevo_falls_back_to_raw_text_when_markdown_absent(app_test_env):
    """
    1. FONCTIONNEL - Fallback corps brut:
    Si ExtractedMarkdownMessage est None ou vide, utilise RawTextBody.
    """
    client, session_maker, _ = app_test_env

    async with session_maker() as session:
        t = await TicketService.create_ticket(session, 1, "u", "Q")
        t_id = t.id

    payload = {
        "items": [
            {
                "From": {"Address": "agent@example.com"},
                "Subject": f"[Ticket #{t_id}]",
                "RawTextBody": "Texte brut de repli",
                "ExtractedMarkdownMessage": None,
            }
        ]
    }

    resp = await client.post(
        f"/api/webhooks/email-inbound/brevo?token={TEST_BREVO_INBOUND_SECRET}",
        json=payload,
    )
    assert resp.status_code == 200

    async with session_maker() as session:
        refreshed = (await session.execute(select(Ticket).where(Ticket.id == t_id))).scalar_one()
        assert refreshed.solution == "Texte brut de repli"


@pytest.mark.asyncio
async def test_webhooks_brevo_partial_batch_failures_returns_200_with_individual_statuses(app_test_env, monkeypatch):
    """
    1. FONCTIONNEL & ROBUSTESSE - Dégradation gracieuse:
    Dans un lot hétérogène (un item valide, un item inconnu, un item sans ID, un item émetteur non autorisé),
    l'échec d'un item ne doit PAS faire échouer l'ensemble du lot HTTP.
    Le code HTTP doit être 200 et chaque item doit reporter son statut précis.
    """
    client, session_maker, _ = app_test_env
    monkeypatch.setattr(settings, "ALLOWED_SUPPORT_EMAIL_SENDERS", "authorized@example.com")

    async with session_maker() as session:
        valid_t = await TicketService.create_ticket(session, 1, "u", "Q")
        valid_id = valid_t.id

    payload = {
        "items": [
            # Item 1: Valide
            {
                "From": {"Address": "authorized@example.com"},
                "Subject": f"[Ticket #{valid_id}] Sol",
                "ExtractedMarkdownMessage": "Solution ok",
            },
            # Item 2: Ticket introuvable
            {
                "From": {"Address": "authorized@example.com"},
                "Subject": "[Ticket #9999999] Sol",
                "ExtractedMarkdownMessage": "Solution introuvable",
            },
            # Item 3: Pas d'ID de ticket
            {
                "From": {"Address": "authorized@example.com"},
                "Subject": "Email sans numéro de ticket",
                "ExtractedMarkdownMessage": "Solution sans id",
            },
            # Item 4: Expéditeur non autorisé
            {
                "From": {"Address": "hacker@evil.com"},
                "Subject": f"[Ticket #{valid_id}] Sol",
                "ExtractedMarkdownMessage": "Solution refusée",
            },
        ]
    }

    response = await client.post(
        f"/api/webhooks/email-inbound/brevo?token={TEST_BREVO_INBOUND_SECRET}",
        json=payload,
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 4

    assert results[0]["status"] == "resolved"
    assert results[1]["status"] == "ticket_not_found"
    assert results[2]["status"] == "no_ticket_reference"
    assert results[3]["status"] == "unauthorized_sender"


@pytest.mark.asyncio
async def test_webhooks_brevo_empty_items_batch_returns_empty_results(app_test_env):
    """
    1. FONCTIONNEL - Cas limite vide:
    Un payload avec une liste items vide renvoie 200 avec results: [].
    """
    client, _, _ = app_test_env
    resp = await client.post(
        f"/api/webhooks/email-inbound/brevo?token={TEST_BREVO_INBOUND_SECRET}",
        json={"items": []},
    )
    assert resp.status_code == 200
    assert resp.json() == {"results": []}


@pytest.mark.asyncio
async def test_webhooks_brevo_idempotence_duplicate_items_in_same_batch(app_test_env):
    """
    1. FONCTIONNEL - Idempotence:
    Si le même ticket apparaît deux fois dans le même lot,
    le premier est 'resolved' et le second est 'already_resolved'.
    """
    client, session_maker, _ = app_test_env
    async with session_maker() as session:
        t = await TicketService.create_ticket(session, 1, "u", "Q")
        t_id = t.id

    payload = {
        "items": [
            {"From": {"Address": "a@ex.com"}, "Subject": f"[Ticket #{t_id}]", "RawTextBody": "Sol 1"},
            {"From": {"Address": "a@ex.com"}, "Subject": f"[Ticket #{t_id}]", "RawTextBody": "Sol 2"},
        ]
    }

    resp = await client.post(
        f"/api/webhooks/email-inbound/brevo?token={TEST_BREVO_INBOUND_SECRET}",
        json=payload,
    )
    assert resp.status_code == 200
    res = resp.json()["results"]
    assert res[0]["status"] == "resolved"
    assert res[1]["status"] == "already_resolved"


# ==============================================================================
# 2. SÉCURITÉ
# ==============================================================================


@pytest.mark.asyncio
async def test_webhooks_brevo_missing_token_returns_401_unauthorized(app_test_env):
    """
    2. SÉCURITÉ - Auth:
    Requête sans paramètre `?token=` renvoie 401.
    """
    client, _, _ = app_test_env
    resp = await client.post(
        "/api/webhooks/email-inbound/brevo",
        json={"items": []},
    )
    assert resp.status_code == 401
    assert "token query parameter" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_webhooks_brevo_invalid_token_returns_401_unauthorized(app_test_env):
    """
    2. SÉCURITÉ - Auth:
    Token invalide renvoie 401.
    """
    client, _, _ = app_test_env
    resp = await client.post(
        "/api/webhooks/email-inbound/brevo?token=faux_token_pirate",
        json={"items": []},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhooks_brevo_secret_not_configured_returns_503_service_unavailable(app_test_env, monkeypatch):
    """
    2. SÉCURITÉ - Fail-closed:
    Si BREVO_INBOUND_SECRET n'est pas configuré, rejet immédiat avec 503.
    """
    client, _, _ = app_test_env
    monkeypatch.setattr(settings, "BREVO_INBOUND_SECRET", None)

    resp = await client.post(
        "/api/webhooks/email-inbound/brevo?token=any",
        json={"items": []},
    )
    assert resp.status_code == 503
    assert "BREVO_INBOUND_SECRET missing" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_webhooks_brevo_unauthenticated_request_rejected_before_json_parsing(app_test_env):
    """
    2. SÉCURITÉ - Masquage du schéma JSON:
    Un appel sans token valide et avec un corps malformé doit être rejeté avec 401,
    sans révéler le schéma d'erreurs 422.
    """
    client, _, _ = app_test_env
    resp = await client.post(
        "/api/webhooks/email-inbound/brevo?token=invalid_token",
        content=b"{ invalid json body }",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhooks_brevo_token_query_parameter_not_leaked_in_application_logs(app_test_env, caplog):
    """
    2. SÉCURITÉ - Secrets dans les logs applicatifs:
    Vérifie que les logs internes de l'application (logger backend) ne loggent pas le token secret.
    Note d'audit: Le passage de secret en query parameter (?token=...) expose néanmoins
    le secret dans les logs d'accès HTTP (ex: uvicorn/httpx/reverse proxies).
    """
    client, _, _ = app_test_env
    with caplog.at_level(logging.DEBUG):
        await client.post(
            f"/api/webhooks/email-inbound/brevo?token={TEST_BREVO_INBOUND_SECRET}",
            json={"items": []},
        )

    backend_records = [r for r in caplog.records if r.name.startswith("backend")]
    for record in backend_records:
        assert TEST_BREVO_INBOUND_SECRET not in record.getMessage()


@pytest.mark.asyncio
async def test_webhooks_brevo_header_auth_x_webhook_token_succes(app_test_env):
    """
    2. SÉCURITÉ - Auth par Header:
    Vérifie qu'un webhook Brevo authentifié par l'en-tête X-Webhook-Token
    est accepté avec succès sans nécessiter de token dans la query string.
    """
    client, session_maker, _ = app_test_env
    async with session_maker() as session:
        t = await TicketService.create_ticket(session, 888, "alice", "Demande header auth")

    payload = {
        "items": [
            {
                "From": {"Address": "agent@example.com"},
                "Subject": f"[Ticket #{t.id}] Résolution via header",
                "RawTextBody": "Solution sécurisée par en-tête",
            }
        ]
    }
    resp = await client.post(
        "/api/webhooks/email-inbound/brevo",
        headers={"X-Webhook-Token": TEST_BREVO_INBOUND_SECRET},
        json=payload,
    )
    assert resp.status_code == 200
    assert resp.json()["results"][0]["status"] == "resolved"


@pytest.mark.asyncio
async def test_webhooks_brevo_header_auth_x_brevo_token_succes(app_test_env):
    """
    2. SÉCURITÉ - Auth par Header:
    Vérifie qu'un webhook Brevo authentifié par l'en-tête alternatif X-Brevo-Token
    est accepté avec succès sans nécessiter de token dans la query string.
    """
    client, session_maker, _ = app_test_env
    async with session_maker() as session:
        t = await TicketService.create_ticket(session, 889, "bob", "Demande alternative header")

    payload = {
        "items": [
            {
                "From": {"Address": "agent@example.com"},
                "Subject": f"[Ticket #{t.id}] Résolution alternative",
                "RawTextBody": "Solution alternative par en-tête",
            }
        ]
    }
    resp = await client.post(
        "/api/webhooks/email-inbound/brevo",
        headers={"X-Brevo-Token": TEST_BREVO_INBOUND_SECRET},
        json=payload,
    )
    assert resp.status_code == 200
    assert resp.json()["results"][0]["status"] == "resolved"


@pytest.mark.asyncio
async def test_webhooks_brevo_access_log_middleware_redacts_query_token_succes(app_test_env, caplog):
    """
    2. SÉCURITÉ - Redaction des logs d'accès HTTP:
    Vérifie que le middleware d'accès et le filtre SensitiveDataFilter
    masquent systématiquement le token query parameter (?token=[REDACTED]).
    """
    client, _, _ = app_test_env
    with caplog.at_level(logging.INFO):
        await client.post(
            f"/api/webhooks/email-inbound/brevo?token={TEST_BREVO_INBOUND_SECRET}",
            json={"items": []},
        )

    backend_records = [r for r in caplog.records if r.name.startswith("backend")]
    # Le secret en clair ne doit jamais apparaître dans les logs du backend
    assert not any(TEST_BREVO_INBOUND_SECRET in r.getMessage() for r in backend_records)
    # Le message du middleware de log d'accès doit contenir [REDACTED]
    redacted_logs = [r.getMessage() for r in backend_records if "[REDACTED]" in r.getMessage()]
    assert len(redacted_logs) >= 1


# ==============================================================================
# 3. ROBUSTESSE
# ==============================================================================


@pytest.mark.asyncio
async def test_webhooks_brevo_exception_in_single_item_handled_as_internal_error(app_test_env):
    """
    3. ROBUSTESSE - Isolation des erreurs de traitement:
    Si une exception imprévue survient lors du traitement d'un élément,
    l'élément est marqué 'internal_error' et les autres éléments du lot sont préservés.
    """
    client, session_maker, _ = app_test_env

    async with session_maker() as session:
        t1 = await TicketService.create_ticket(session, 1, "u1", "Q1")
        t2 = await TicketService.create_ticket(session, 2, "u2", "Q2")

    # Patch _resolve_inbound_email pour crasher uniquement sur le ticket 1
    from backend.main import _resolve_inbound_email
    orig_fn = _resolve_inbound_email

    async def mock_resolve_item(*args, **kwargs):
        subject = kwargs.get("subject", "")
        if f"Ticket #{t1.id}" in subject:
            raise RuntimeError("Unexpected boom in item 1")
        return await orig_fn(*args, **kwargs)

    payload = {
        "items": [
            {"From": {"Address": "a@ex.com"}, "Subject": f"[Ticket #{t1.id}]", "RawTextBody": "Sol 1"},
            {"From": {"Address": "a@ex.com"}, "Subject": f"[Ticket #{t2.id}]", "RawTextBody": "Sol 2"},
        ]
    }

    with patch("backend.main._resolve_inbound_email", side_effect=mock_resolve_item):
        resp = await client.post(
            f"/api/webhooks/email-inbound/brevo?token={TEST_BREVO_INBOUND_SECRET}",
            json=payload,
        )

    assert resp.status_code == 200
    results = resp.json()["results"]
    assert results[0]["status"] == "internal_error"
    assert results[1]["status"] == "resolved"


@pytest.mark.asyncio
async def test_webhooks_brevo_large_batch_preloading_performance(app_test_env):
    """
    3. ROBUSTESSE - Performance et batch pre-fetch:
    Vérifie qu'un lot de 15 tickets est pré-chargé et résolu efficacement.
    """
    client, session_maker, _ = app_test_env

    ticket_ids = []
    async with session_maker() as session:
        for i in range(15):
            t = await TicketService.create_ticket(session, 100 + i, f"u{i}", f"Question {i}")
            ticket_ids.append(t.id)

    items = [
        {
            "From": {"Address": f"agent{i}@example.com"},
            "Subject": f"[Ticket #{t_id}] Réponse {i}",
            "ExtractedMarkdownMessage": f"Solution {i}",
        }
        for i, t_id in enumerate(ticket_ids)
    ]

    resp = await client.post(
        f"/api/webhooks/email-inbound/brevo?token={TEST_BREVO_INBOUND_SECRET}",
        json={"items": items},
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 15
    assert all(r["status"] == "resolved" for r in results)
