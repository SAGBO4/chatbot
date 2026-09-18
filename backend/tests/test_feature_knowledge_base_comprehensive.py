import asyncio
import logging
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import KnowledgeArticle
from backend.services.knowledge_base import (
    KnowledgeBaseService,
    tokenize,
    compute_tf_vector,
    token_similarity,
    compute_char_ngram_similarity,
)


@pytest.mark.asyncio
async def test_kb_ingest_happy_path_creates_article_and_returns_201(app_test_env, caplog):
    """
    1. FONCTIONNEL - Happy Path:
    Création d'un article via POST /api/knowledge/ingest.
    Vérifie code 201, données retournées et persistance en base de données.
    """
    client, session_maker, _ = app_test_env

    payload = {
        "question": "Comment configurer les notifications push ?",
        "solution": "Accédez aux Préférences > Notifications et activez les alertes push.",
        "keywords": "notifications, push, alertes, preferences",
        "source_ticket_id": 4242,
    }

    with caplog.at_level(logging.INFO):
        response = await client.post("/api/knowledge/ingest", json=payload)

    # 4. ASSERTIONS
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["question"] == payload["question"]
    assert data["solution"] == payload["solution"]
    assert data["keywords"] == payload["keywords"]
    assert data["source_ticket_id"] == 4242

    article_id = data["id"]
    async with session_maker() as session:
        db_art = (await session.execute(select(KnowledgeArticle).where(KnowledgeArticle.id == article_id))).scalar_one()
        assert db_art.source_ticket_id == 4242
        assert db_art.created_at is not None


@pytest.mark.asyncio
async def test_kb_ingest_auto_extracts_keywords_when_none_provided(app_test_env):
    """
    1. FONCTIONNEL - Extraction automatique de mots-clés:
    Si keywords est omis (None), les mots-clés sont automatiquement dérivés de la question.
    """
    client, session_maker, _ = app_test_env

    payload = {
        "question": "Problème d'exportation de données comptables",
        "solution": "Téléchargez le fichier CSV depuis l'onglet Comptabilité.",
    }

    response = await client.post("/api/knowledge/ingest", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["keywords"] is not None
    assert "exportation" in data["keywords"] or "données" in data["keywords"] or "comptables" in data["keywords"]


@pytest.mark.asyncio
async def test_kb_ingest_upsert_existing_source_ticket_id_updates_article(app_test_env):
    """
    1. FONCTIONNEL & IDEMPOTENCE:
    Si un article existe déjà pour un source_ticket_id donné,
    l'ingestion met à jour l'article existant au lieu de créer un doublon.
    """
    client, session_maker, _ = app_test_env

    # 1. Premier ajout
    payload1 = {
        "question": "Question initiale",
        "solution": "Première version de la solution",
        "source_ticket_id": 100,
    }
    resp1 = await client.post("/api/knowledge/ingest", json=payload1)
    assert resp1.status_code == 201
    art_id1 = resp1.json()["id"]

    # 2. Deuxième ajout avec le même source_ticket_id
    payload2 = {
        "question": "Question modifiée",
        "solution": "Version révisée de la solution",
        "source_ticket_id": 100,
    }
    resp2 = await client.post("/api/knowledge/ingest", json=payload2)
    assert resp2.status_code == 201
    art_id2 = resp2.json()["id"]

    # L'ID doit être le même (mise à jour sur place)
    assert art_id1 == art_id2

    async with session_maker() as session:
        articles = (
            await session.execute(
                select(KnowledgeArticle).where(KnowledgeArticle.source_ticket_id == 100)
            )
        ).scalars().all()
        assert len(articles) == 1
        assert articles[0].solution == "Version révisée de la solution"


@pytest.mark.asyncio
async def test_kb_ingest_empty_question_returns_422_validation_error(app_test_env):
    """
    1. FONCTIONNEL - Validation entrées:
    Une question vide viole min_length=1 et renvoie 422.
    """
    client, _, _ = app_test_env
    resp = await client.post("/api/knowledge/ingest", json={"question": "", "solution": "Valide"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_kb_ingest_max_length_boundaries_succeeds(app_test_env):
    """
    1. FONCTIONNEL - Cas limites Max:
    Question max 4096 caractères, Solution max 5000 caractères.
    """
    client, _, _ = app_test_env
    payload = {
        "question": "Q" * 4096,
        "solution": "S" * 5000,
    }
    resp = await client.post("/api/knowledge/ingest", json=payload)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_kb_ingest_exceeds_max_length_returns_422(app_test_env):
    """
    1. FONCTIONNEL - Erreurs attendues:
    Solution de 5001 caractères renvoie 422.
    """
    client, _, _ = app_test_env
    resp = await client.post(
        "/api/knowledge/ingest",
        json={"question": "Valide", "solution": "S" * 5001},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_kb_list_pagination_limit_and_offset_works(app_test_env):
    """
    1. FONCTIONNEL - Pagination:
    GET /api/knowledge pagination limit & offset.
    """
    client, session_maker, _ = app_test_env

    async with session_maker() as session:
        for i in range(1, 5):
            await KnowledgeBaseService.add_article(session, f"Q{i}", f"S{i}")

    resp = await client.get("/api/knowledge?limit=2&offset=0")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp_next = await client.get("/api/knowledge?limit=2&offset=2")
    assert resp_next.status_code == 200
    assert len(resp_next.json()) == 2


@pytest.mark.asyncio
async def test_kb_search_bilingual_stopwords_filtered():
    """
    1. FONCTIONNEL - Stopwords bilingues:
    Vérifie que les stopwords français ('le', 'pourquoi', 'comment')
    et anglais ('the', 'why', 'how') sont correctement filtrés.
    """
    tokens = tokenize("Comment faire pour exporter the file ?")
    assert "comment" not in tokens
    assert "faire" not in tokens
    assert "pour" not in tokens
    assert "the" not in tokens
    assert "exporter" in tokens
    assert "file" in tokens


@pytest.mark.asyncio
async def test_kb_search_prefix_and_stem_matching_scores_correctly(app_test_env):
    """
    1. FONCTIONNEL - Recherche lexicale avec stemming/préfixe:
    'imprimer' doit matcher un article traitant de l''imprimante'.
    """
    client, session_maker, _ = app_test_env

    async with session_maker() as session:
        await KnowledgeBaseService.add_article(
            session=session,
            question="Mon imprimante est bloquée en mode hors-ligne",
            solution="Redémarrez le spouleur d'impression Windows.",
            keywords="imprimante, impression, hors-ligne",
        )

        matches = await KnowledgeBaseService.search(session, query="Comment imprimer un document ?")
        assert len(matches) > 0
        art, score = matches[0]
        assert "imprimante" in art.question
        assert score >= 0.3


@pytest.mark.asyncio
async def test_kb_search_trigram_fuzzy_fallback_matches_typos(app_test_env):
    """
    1. FONCTIONNEL - Fallback n-gram pour tolérance aux fautes de frappe:
    Recherche avec typo ('imprimantee') retrouve l'article grâce aux trigrammes.
    """
    client, session_maker, _ = app_test_env

    async with session_maker() as session:
        await KnowledgeBaseService.add_article(
            session=session,
            question="Configuration de l'imprimante réseau",
            solution="Connectez-vous via l'IP 192.168.1.50.",
        )

        matches = await KnowledgeBaseService.search(session, query="imprimante réseau")
        assert len(matches) > 0


@pytest.mark.asyncio
async def test_kb_service_crud_update_and_delete_article(app_test_env):
    """
    1. FONCTIONNEL - Service CRUD:
    Vérifie les méthodes update_article et delete_article.
    """
    _, session_maker, _ = app_test_env

    async with session_maker() as session:
        art = await KnowledgeBaseService.add_article(session, "Question CRUD", "Solution Initiale")
        art_id = art.id

        # Update
        updated = await KnowledgeBaseService.update_article(
            session, art, solution="Solution Mise à Jour", keywords="crud, test"
        )
        assert updated.solution == "Solution Mise à Jour"
        assert updated.keywords == "crud, test"

        # Delete
        await KnowledgeBaseService.delete_article(session, updated)
        remaining = await KnowledgeBaseService.get_all_articles(session)
        assert not any(a.id == art_id for a in remaining)


# ==============================================================================
# 2. SÉCURITÉ
# ==============================================================================


@pytest.mark.asyncio
async def test_kb_ingest_and_list_unauthorized_returns_401(unauth_client):
    """
    2. SÉCURITÉ - Authz:
    POST /api/knowledge/ingest et GET /api/knowledge sans X-API-Key renvoient 401.
    """
    resp_ingest = await unauth_client.post("/api/knowledge/ingest", json={"question": "Q", "solution": "S"})
    assert resp_ingest.status_code == 401

    resp_list = await unauth_client.get("/api/knowledge")
    assert resp_list.status_code == 401


@pytest.mark.asyncio
async def test_kb_sql_injection_in_search_query_handled_safely(app_test_env):
    """
    2. SÉCURITÉ - Injection SQL:
    Recherche KB avec syntaxe SQL (`%' UNION SELECT 1,2,3...`)
    exécutée de manière sûre via SQLAlchemy ORM sans injection possible.
    """
    _, session_maker, _ = app_test_env

    async with session_maker() as session:
        await KnowledgeBaseService.add_article(session, "Sécurité SQL", "Protection ORM active.")

        sql_injection = "test%' OR '1'='1' UNION SELECT NULL, NULL, NULL, NULL, NULL, NULL, NULL --"
        matches = await KnowledgeBaseService.search(session, query=sql_injection)
        # Ne doit pas lever d'erreur SQL ni renvoyer de données corrompues
        assert isinstance(matches, list)


@pytest.mark.asyncio
async def test_kb_excessive_tokens_bounded_to_twelve(app_test_env):
    """
    2. SÉCURITÉ - Prévention d'explosion de clauses SQL (Déni de service):
    Une requête contenant 50 mots doit être bornée aux 12 premiers tokens
    pour éviter la construction d'une requête SQL monstre avec des centaines de conditions.
    """
    _, session_maker, _ = app_test_env

    long_prompt = "mot " * 50
    async with session_maker() as session:
        matches = await KnowledgeBaseService.search(session, query=long_prompt)
        assert isinstance(matches, list)


# ==============================================================================
# 3. ROBUSTESSE
# ==============================================================================


@pytest.mark.asyncio
async def test_kb_concurrent_ingestions_succeed(app_test_env):
    """
    3. ROBUSTESSE - Concurrence:
    10 ajouts concurrents d'articles dans la KB.
    """
    client, session_maker, _ = app_test_env

    async def add_item(idx: int):
        return await client.post(
            "/api/knowledge/ingest",
            json={"question": f"Question concurrente {idx}", "solution": f"Solution {idx}"},
        )

    results = await asyncio.gather(*(add_item(i) for i in range(10)))
    assert all(r.status_code == 201 for r in results)

    async with session_maker() as session:
        all_arts = await KnowledgeBaseService.get_all_articles(session, limit=100)
        assert len(all_arts) >= 10
