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
