"""DATABASE_URL as PaaS providers write it (Heroku, Dokku: `postgres://`) must reach SQLAlchemy's async driver."""
import pytest

from app.config import Settings


@pytest.mark.parametrize(
    "given,expected",
    [
        ("postgres://u:p@db:5432/app", "postgresql+asyncpg://u:p@db:5432/app"),
        ("postgresql://u:p@db:5432/app", "postgresql+asyncpg://u:p@db:5432/app"),
        ("postgresql+asyncpg://u:p@db:5432/app", "postgresql+asyncpg://u:p@db:5432/app"),
        ("sqlite+aiosqlite:///./data/chatbot.db", "sqlite+aiosqlite:///./data/chatbot.db"),
    ],
)
def test_database_url_is_normalized_for_the_async_driver(given, expected):
    assert Settings(DATABASE_URL=given).DATABASE_URL == expected
