import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.database import init_db
from backend.services.knowledge_base import KnowledgeBaseService


@pytest_asyncio.fixture
async def async_session(tmp_path):
    db_file = tmp_path / "kb_test.db"
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)
    await init_db(db_engine=test_engine)

    session_maker = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_maker() as session:
        yield session

    await test_engine.dispose()


@pytest.mark.asyncio
async def test_add_and_search_article(async_session):
    # Add articles
    await KnowledgeBaseService.add_article(
        session=async_session,
        question="Comment réinitialiser mon mot de passe ?",
        solution="Rendez-vous sur la page login et cliquez sur Mot de passe oublié.",
        keywords="mot de passe, password, reset, login",
    )
    await KnowledgeBaseService.add_article(
        session=async_session,
        question="Quels sont les horaires d'ouverture du support ?",
        solution="Le support est ouvert du lundi au vendredi de 9h à 18h.",
        keywords="support, horaires, contact, téléphone",
    )

    # Search for password reset
    results = await KnowledgeBaseService.search(
        session=async_session,
        query="J'ai oublié mon mot de passe comment faire",
        threshold=0.3,
    )
    assert len(results) >= 1
    best_article, score = results[0]
    assert "mot de passe" in best_article.question
    assert score >= 0.3

    # Search for something unrelated
    unrelated_results = await KnowledgeBaseService.search(
        session=async_session,
        query="Comment faire une pizza margherita avec du basilic frais",
        threshold=0.3,
    )
    assert len(unrelated_results) == 0


@pytest.mark.asyncio
async def test_dynamic_ingestion_and_immediate_retrieval(async_session):
    # Ingest a new solution from support
    new_article = await KnowledgeBaseService.add_article(
        session=async_session,
        question="Erreur 502 Bad Gateway au paiement",
        solution="Videz le cache de votre navigateur ou utilisez une carte bancaire différente.",
        keywords="paiement, 502, erreur, carte",
        source_ticket_id=42,
    )
    assert new_article.id is not None
    assert new_article.source_ticket_id == 42

    # Query immediately
    results = await KnowledgeBaseService.search(
        session=async_session,
        query="J'ai une erreur 502 quand je tente de payer",
        threshold=0.3,
    )
    assert len(results) >= 1
    assert results[0][0].id == new_article.id
    assert "cache" in results[0][0].solution


@pytest.mark.asyncio
async def test_knowledge_base_deduplication_by_source_ticket_id(async_session):
    art1 = await KnowledgeBaseService.add_article(
        session=async_session,
        question="First question",
        solution="First solution",
        source_ticket_id=101,
    )
    assert art1.id is not None
    initial_id = art1.id

    # Re-ingest with the same source_ticket_id
    art2 = await KnowledgeBaseService.add_article(
        session=async_session,
        question="Updated question",
        solution="Updated solution",
        source_ticket_id=101,
    )
    assert art2.id == initial_id
    assert art2.solution == "Updated solution"

    all_arts = await KnowledgeBaseService.get_all_articles(async_session)
    matching = [a for a in all_arts if a.source_ticket_id == 101]
    assert len(matching) == 1


def test_bilingual_tokenization():
    from backend.services.knowledge_base import tokenize
    # English stopwords like 'how', 'can', 'my' must be filtered
    tokens_en = tokenize("How can I reset my password?")
    assert "how" not in tokens_en
    assert "can" not in tokens_en
    assert "my" not in tokens_en
    assert "reset" in tokens_en
    assert "password" in tokens_en

    # French stopwords like 'comment', 'faire', 'mon' must be filtered
    tokens_fr = tokenize("Comment faire pour modifier mon compte ?")
    assert "comment" not in tokens_fr
    assert "faire" not in tokens_fr
    assert "mon" not in tokens_fr
    assert "modifier" in tokens_fr
    assert "compte" in tokens_fr


@pytest.mark.asyncio
async def test_knowledge_base_pagination(async_session):
    for i in range(15):
        await KnowledgeBaseService.add_article(
            session=async_session,
            question=f"Question #{i}",
            solution=f"Solution #{i}",
        )

    # Page 1: limit 5, offset 0
    page1 = await KnowledgeBaseService.get_all_articles(async_session, limit=5, offset=0)
    assert len(page1) == 5

    # Page 2: limit 5, offset 5
    page2 = await KnowledgeBaseService.get_all_articles(async_session, limit=5, offset=5)
    assert len(page2) == 5

    # Verify no overlap between page 1 and page 2
    page1_ids = {a.id for a in page1}
    page2_ids = {a.id for a in page2}
    assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.asyncio
async def test_search_with_tokenless_or_punctuation_query_returns_empty(async_session):
    await KnowledgeBaseService.add_article(
        session=async_session,
        question="Comment faire ?",
        solution="Voici la solution.",
    )
    # Query with punctuation only or empty tokens
    results = await KnowledgeBaseService.search(
        session=async_session,
        query="??? !!! ...",
    )
    assert results == []


@pytest.mark.asyncio
async def test_fuzzy_search_finds_article_beyond_200(async_session):
    # Insert old target article (id = 1)
    old_art = await KnowledgeBaseService.add_article(
        session=async_session,
        question="Configuration spécifique kubernetes ingress",
        solution="Configurez les annotations ingress-nginx.",
    )

    # Insert 205 filler articles so old_art is outside the top 200 most recent articles
    for i in range(205):
        await KnowledgeBaseService.add_article(
            session=async_session,
            question=f"Autre question unrelated {i}",
            solution=f"Autre solution {i}",
        )

    # Query with fuzzy variations / typos that won't match the 4-char prefix SQL LIKE but match n-gram
    results = await KnowledgeBaseService.search(
        session=async_session,
        query="xkuberneetes xingress",
        threshold=0.2,
    )
    assert len(results) >= 1
    assert results[0][0].id == old_art.id

