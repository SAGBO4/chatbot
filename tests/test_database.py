import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from backend.models import Base, Ticket, KnowledgeArticle, TicketStatus
from backend.database import init_db


@pytest.mark.asyncio
async def test_database_initialization_and_models(tmp_path):
    db_file = tmp_path / "test.db"
    test_db_url = f"sqlite+aiosqlite:///{db_file}"
    test_engine = create_async_engine(test_db_url, echo=False)

    await init_db(db_engine=test_engine)

    test_session_maker = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with test_session_maker() as session:
        # Test KnowledgeArticle insertion
        article = KnowledgeArticle(
            question="Comment réinitialiser mon mot de passe ?",
            solution="Cliquez sur 'Mot de passe oublié' sur la page de connexion.",
            keywords="mot de passe, réinitialisation, login",
        )
        session.add(article)

        # Test Ticket insertion
        ticket = Ticket(
            user_id=123456789,
            user_handle="john_doe",
            question="Mon compte est bloqué",
            status=TicketStatus.OPEN.value,
        )
        session.add(ticket)
        await session.commit()

        # Query back
        res_article = await session.execute(
            select(KnowledgeArticle).where(KnowledgeArticle.question.like("%mot de passe%"))
        )
        found_article = res_article.scalars().first()
        assert found_article is not None
        assert "mot de passe" in found_article.question
        assert found_article.id == 1

        res_ticket = await session.execute(
            select(Ticket).where(Ticket.user_id == 123456789)
        )
        found_ticket = res_ticket.scalars().first()
        assert found_ticket is not None
        assert found_ticket.status == TicketStatus.OPEN.value
        assert found_ticket.user_handle == "john_doe"

    await test_engine.dispose()
