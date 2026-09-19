import logging

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, inspect, text
from app.models import Base, Ticket, KnowledgeArticle, TicketStatus
from app.config import settings
from app.database import init_db, run_alembic_upgrade


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


@pytest.mark.asyncio
async def test_init_db_backfills_missing_columns_on_existing_deployment(tmp_path):
    """
    Simulates a deployment whose `chatbot.db` predates the
    `resolution_channel` / `support_group_message_id` columns: init_db()
    must ALTER the existing table rather than leave it stuck on the old
    schema (create_all alone is CREATE TABLE IF NOT EXISTS and never
    touches a table that already exists).
    """
    db_file = tmp_path / "legacy.db"
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)

    # Build the *old* tickets table by hand, without the two new columns.
    async with test_engine.begin() as conn:
        await conn.execute(
            text(
                """
                CREATE TABLE tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    user_handle VARCHAR(255),
                    question TEXT NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    automated_answer TEXT,
                    solution TEXT,
                    resolved_by VARCHAR(255),
                    created_at DATETIME NOT NULL,
                    resolved_at DATETIME
                )
                """
            )
        )
        await conn.execute(
            text(
                "INSERT INTO tickets (user_id, question, status, created_at) "
                "VALUES (42, 'Pre-existing ticket', 'OPEN', '2026-01-01 00:00:00')"
            )
        )

    # Upgrading the app now runs init_db() against this pre-existing database.
    await init_db(db_engine=test_engine)

    async with test_engine.connect() as conn:
        columns = await conn.run_sync(
            lambda sync_conn: {c["name"] for c in inspect(sync_conn).get_columns("tickets")}
        )
    assert "resolution_channel" in columns
    assert "support_group_message_id" in columns

    test_session_maker = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with test_session_maker() as session:
        # The query that used to 500 with "no such column" now succeeds and
        # the pre-existing row survives with the new columns defaulting to NULL.
        result = await session.execute(select(Ticket).where(Ticket.user_id == 42))
        ticket = result.scalars().first()
        assert ticket is not None
        assert ticket.resolution_channel is None
        assert ticket.support_group_message_id is None

    await test_engine.dispose()


@pytest.fixture
def restore_root_logging():
    """alembic's fileConfig() rewrites the root logger; put it back so other tests are unaffected."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)


def test_alembic_upgrade_does_not_disable_application_loggers(tmp_path, monkeypatch, restore_root_logging):
    """
    The migration runs in the same process as the API at startup. alembic/env.py calls
    logging.config.fileConfig(), which by default disables every logger that already exists: after
    startup, app.main, the services, httpx and uvicorn.error stopped logging (errors included).
    """
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'migrated.db'}")
    existing = [logging.getLogger(name) for name in ("app.main", "app.services.telegram_relay", "httpx")]

    run_alembic_upgrade()

    assert (tmp_path / "migrated.db").exists(), "the migration did not run: this test would pass vacuously"
    assert [logger.name for logger in existing if logger.disabled] == []
