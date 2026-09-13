from typing import AsyncGenerator
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


async def init_db(db_engine=None) -> None:
    target_engine = db_engine or engine
    async with target_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
