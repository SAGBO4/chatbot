"""The knowledge base seed script and its data file."""
import pytest

from app.services.knowledge_base import KnowledgeBaseService
from scripts import seed_knowledge_base as seed


def test_seed_file_is_well_formed():
    articles, retired = seed.load_seed()

    assert len(articles) >= 20
    questions = [question.strip() for question, _, _ in articles]
    assert len(set(questions)) == len(questions), "duplicate question in the seed file"
    for question, solution, keywords in articles:
        assert question.strip() and solution.strip() and keywords.strip(), question
    assert not set(retired) & set(questions), "a question cannot be both seeded and retired"


@pytest.mark.asyncio
async def test_seed_script_is_idempotent(app_test_env, monkeypatch, capsys):
    _, session_maker, engine = app_test_env

    async def no_init_db():
        return None

    monkeypatch.setattr(seed, "async_session_maker", session_maker)
    monkeypatch.setattr(seed, "init_db", no_init_db)
    articles, _ = seed.load_seed()

    await seed.main()
    async with session_maker() as session:
        first = len(await KnowledgeBaseService.get_all_articles(session))
    assert first == len(articles)

    capsys.readouterr()
    await seed.main()
    async with session_maker() as session:
        second = len(await KnowledgeBaseService.get_all_articles(session))
    assert second == first
    assert "Added" not in capsys.readouterr().out
