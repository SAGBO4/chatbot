from typing import AsyncGenerator, Optional
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.config import settings
from backend.models import Base

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
)

async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def _add_missing_columns(sync_conn) -> None:
    """
    Adds to already-existing tables any column declared on the ORM models but
    absent from the live schema, so a deployment that already has a database
    file (e.g. the `chatbot.db` volume in docker-compose) picks up new
    columns instead of failing every query with "no such column" once the
    app starts selecting them.

    `Base.metadata.create_all` (run just before this) only issues
    `CREATE TABLE IF NOT EXISTS`, so it never alters a table that already
    exists. This project has no migrations framework, and every column added
    after a table's initial release is nullable, so a plain `ADD COLUMN` is
    sufficient and safe on both SQLite and Postgres.
    """
    inspector = inspect(sync_conn)
    existing_tables = set(inspector.get_table_names())
    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # brand-new table, create_all already gave it every column
        existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing_columns:
                continue
            ddl_type = column.type.compile(dialect=sync_conn.dialect)
            sync_conn.execute(
                text(f'ALTER TABLE {table.name} ADD COLUMN {column.name} {ddl_type}')
            )


import os
import logging
from pathlib import Path
from alembic.config import Config
from alembic import command

logger = logging.getLogger(__name__)


def run_alembic_upgrade(connection_url: Optional[str] = None) -> None:
    """Runs Alembic migrations up to head revision programmatically."""
    ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    if ini_path.exists():
        alembic_cfg = Config(str(ini_path))
        url = connection_url or settings.DATABASE_URL
        alembic_cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(alembic_cfg, "head")


async def init_db(db_engine=None) -> None:
    target_engine = db_engine or engine
    # For standard application startup on the configured database, run Alembic migrations
    if db_engine is None:
        if "sqlite" in settings.DATABASE_URL:
            db_path_str = settings.DATABASE_URL.split(":///")[-1]
            if db_path_str:
                Path(db_path_str).resolve().parent.mkdir(parents=True, exist_ok=True)
        try:
            run_alembic_upgrade()
            logger.info("Alembic migrations applied successfully.")
        except Exception as exc:
            logger.warning("Alembic upgrade encountered an issue, falling back to direct metadata sync: %s", exc)

    async with target_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
