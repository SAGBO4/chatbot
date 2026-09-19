import asyncio
import logging
from pathlib import Path
from typing import AsyncGenerator, Optional
from alembic.config import Config
from alembic import command
from sqlalchemy import inspect, text, event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings
from app.models import Base

logger = logging.getLogger(__name__)

engine_kwargs = {
    "echo": False,
    "pool_pre_ping": True,
}
if "sqlite" not in settings.DATABASE_URL:
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
    })

engine = create_async_engine(
    settings.DATABASE_URL,
    **engine_kwargs,
)


@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enables WAL mode, busy timeout and foreign keys for high concurrency on SQLite."""
    if "sqlite" in settings.DATABASE_URL:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.close()


async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def _add_missing_columns(sync_conn) -> None:
    """
    Safety net for databases that predate the Alembic migrations, or when the upgrade fails.

    Adds any column declared on the ORM models but missing from an existing table, so the app
    does not fail with "no such column". `create_all` only issues `CREATE TABLE IF NOT EXISTS`
    and never alters an existing table. Columns added after a table's first release are
    nullable, so a plain `ADD COLUMN` is safe on both SQLite and Postgres.
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
                text(f'ALTER TABLE {table.name} ADD COLUMN {column.name} {ddl_type}')  # nosemgrep
            )


def run_alembic_upgrade(connection_url: Optional[str] = None) -> None:
    """Runs Alembic migrations up to head revision programmatically."""
    ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    if ini_path.exists():
        alembic_cfg = Config(str(ini_path))
        url = connection_url or settings.DATABASE_URL
        alembic_cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(alembic_cfg, "head")


async def init_db(db_engine=None) -> None:
    """
    Prepare the schema. Without `db_engine` (normal startup) it first runs the Alembic
    migrations, falling back to a warning if they fail; then `create_all` and
    `_add_missing_columns` make sure every table and column exists.
    """
    target_engine = db_engine or engine
    if db_engine is None:
        if "sqlite" in settings.DATABASE_URL:
            db_path_str = settings.DATABASE_URL.split(":///")[-1]
            if db_path_str:
                Path(db_path_str).resolve().parent.mkdir(parents=True, exist_ok=True)
        try:
            await asyncio.to_thread(run_alembic_upgrade)
            logger.info("Alembic migrations applied successfully.")
        except Exception as exc:
            logger.warning("Alembic upgrade encountered an issue, falling back to direct metadata sync: %s", exc)

    async with target_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: one database session per request."""
    async with async_session_maker() as session:
        yield session
