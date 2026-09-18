import time
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message, User, Chat

from bot.middlewares.throttling import ThrottlingMiddleware
from backend.limiter import limiter


@pytest.mark.asyncio
async def test_throttling_messages_under_rate_limit_are_allowed():
    """
    1. FONCTIONNEL:
    Les messages inférieurs à la limite (4 messages avec limite=5)
    doivent tous être transmis au handler.
    """
    middleware = ThrottlingMiddleware(rate_limit=5, window_seconds=10.0)
    handler = AsyncMock(return_value="OK")

    user = MagicMock(spec=User, id=42)
    message = MagicMock(spec=Message, from_user=user)

    for _ in range(4):
        res = await middleware(handler, message, {})
        assert res == "OK"

    assert handler.call_count == 4


@pytest.mark.asyncio
async def test_throttling_excess_messages_dropped_and_warning_sent():
    """
    1. FONCTIONNEL & SÉCURITÉ:
    Le 6ème message envoyé dans la fenêtre dépasse la limite (5).
    Il doit être bloqué (retourne None sans appeler le handler) et un avertissement est envoyé.
    """
    middleware = ThrottlingMiddleware(rate_limit=5, window_seconds=10.0, warning_cooldown=5.0)
    handler = AsyncMock(return_value="OK")

    user = MagicMock(spec=User, id=42)
    message = MagicMock(spec=Message, from_user=user)
    message.answer = AsyncMock()

    # 5 messages autorisés
    for _ in range(5):
        res = await middleware(handler, message, {})
        assert res == "OK"

    # 6ème message bloqué
    res_blocked = await middleware(handler, message, {})
    assert res_blocked is None
    assert handler.call_count == 5

    # Avertissement envoyé à l'utilisateur
    message.answer.assert_called_once()
    assert "Veuillez patienter" in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_throttling_warning_cooldown_prevents_repeated_warning_spam():
    """
    1. FONCTIONNEL:
    Pendant la période de cooldown d'avertissement, les messages excédentaires
    sont silencieusement ignorés sans spammer l'utilisateur de messages d'avertissement.
    """
    middleware = ThrottlingMiddleware(rate_limit=2, window_seconds=10.0, warning_cooldown=5.0)
    handler = AsyncMock(return_value="OK")

    user = MagicMock(spec=User, id=42)
    message = MagicMock(spec=Message, from_user=user)
    message.answer = AsyncMock()

    # 2 autorisés
    await middleware(handler, message, {})
    await middleware(handler, message, {})

    # 3ème: bloqué + avertissement 1
    await middleware(handler, message, {})
    assert message.answer.call_count == 1

    # 4ème: bloqué, mais pas de nouvel avertissement (cooldown actif)
    await middleware(handler, message, {})
    assert message.answer.call_count == 1


@pytest.mark.asyncio
async def test_throttling_per_user_isolation_one_user_limit_does_not_block_another_user():
    """
    2. SÉCURITÉ - Isolation des utilisateurs:
    Le dépassement de quota par l'utilisateur A ne doit en aucun cas bloquer l'utilisateur B.
    """
    middleware = ThrottlingMiddleware(rate_limit=2, window_seconds=10.0)
    handler = AsyncMock(return_value="OK")

    user_a = MagicMock(spec=User, id=101)
    user_b = MagicMock(spec=User, id=202)

    msg_a = MagicMock(spec=Message, from_user=user_a)
    msg_a.answer = AsyncMock()
    msg_b = MagicMock(spec=Message, from_user=user_b)
    msg_b.answer = AsyncMock()

    # User A consomme ses 2 requêtes et se fait bloquer à la 3e
    await middleware(handler, msg_a, {})
    await middleware(handler, msg_a, {})
    res_a3 = await middleware(handler, msg_a, {})
    assert res_a3 is None

    # User B doit pouvoir envoyer ses messages normalement
    res_b1 = await middleware(handler, msg_b, {})
    assert res_b1 == "OK"


@pytest.mark.slow
@pytest.mark.asyncio
async def test_throttling_sliding_window_expiration_allows_new_messages():
    """
    1. FONCTIONNEL & ROBUSTESSE - Expiration fenêtre glissante (marqué @pytest.mark.slow):
    Après expiration de la fenêtre temporelle, l'utilisateur retrouve son droit de message.
    """
    # Fenêtre très courte de 0.2s pour le test
    middleware = ThrottlingMiddleware(rate_limit=1, window_seconds=0.2)
    handler = AsyncMock(return_value="OK")

    user = MagicMock(spec=User, id=77)
    msg = MagicMock(spec=Message, from_user=user)
    msg.answer = AsyncMock()

    # 1er message OK
    res1 = await middleware(handler, msg, {})
    assert res1 == "OK"

    # Immédiatement après: bloqué
    res2 = await middleware(handler, msg, {})
    assert res2 is None

    # Attente expiration fenêtre
    time.sleep(0.25)

    # Nouveau message autorisé
    res3 = await middleware(handler, msg, {})
    assert res3 == "OK"


@pytest.mark.asyncio
async def test_ratelimit_backend_tickets_exceeding_limit_returns_429(app_test_env):
    """
    1. FONCTIONNEL / 2. SÉCURITÉ - Limiteur backend FastAPI:
    L'endpoint POST /api/tickets est limité à 10/minute.
    La 11ème requête doit retourner 429 Too Many Requests.
    """
    client, _, _ = app_test_env
    limiter.enabled = True
    limiter.reset()

    try:
        # Envoi de 10 requêtes valides
        for i in range(10):
            resp = await client.post(
                "/api/tickets",
                json={"user_id": 1, "question": f"Question {i}"},
            )
            assert resp.status_code == 201

        # 11ème requête -> 429
        resp_blocked = await client.post(
            "/api/tickets",
            json={"user_id": 1, "question": "Question 11 excédentaire"},
        )
        assert resp_blocked.status_code == 429
        data = resp_blocked.json()
        assert "Rate limit exceeded" in data["detail"]
        assert "error" in data
    finally:
        limiter.reset()
        limiter.enabled = False
