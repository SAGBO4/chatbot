"""Seed the knowledge base with the initial Stack Wallet support content.

Usage:
    python -m scripts.seed_knowledge_base

The content lives in `scripts/knowledge_base_seed.json`: edit that file to reuse this bot for
another product. The script is idempotent (adds, updates or leaves each article as is).
"""
import asyncio
import json
from pathlib import Path

from app.database import async_session_maker, init_db
from app.services.knowledge_base import KnowledgeBaseService

SEED_FILE = Path(__file__).with_name("knowledge_base_seed.json")


def load_seed(path: Path = SEED_FILE) -> tuple[list[tuple[str, str, str]], list[str]]:
    """
    Read the seed file: `(articles, retired_questions)`, each article a `(question, solution, keywords)`.

    Keywords cover both FR and EN terms so the lexical search matches questions asked in either
    language. `retired_questions` are entries from earlier revisions that were merged into another
    one; they are deleted, so re-running the script also cleans an already-seeded database.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    articles = [(a["question"], a["solution"], a["keywords"]) for a in data["articles"]]
    return articles, data["retired_questions"]


async def main() -> None:
    articles, retired_questions = load_seed()
    await init_db()
    async with async_session_maker() as session:
        for question in retired_questions:
            article = await KnowledgeBaseService.get_article_by_question(session, question.strip())
            if article:
                await KnowledgeBaseService.delete_article(session, article)
                print(f"Deleted retired article #{article.id}: {question[:60]}...")

        for question, solution, keywords in articles:
            article = await KnowledgeBaseService.get_article_by_question(session, question.strip())
            if article is None:
                article = await KnowledgeBaseService.add_article(
                    session=session,
                    question=question,
                    solution=solution,
                    keywords=keywords,
                )
                print(f"Added article #{article.id}: {article.question[:60]}...")
            elif article.solution.strip() != solution.strip() or (article.keywords or "").strip() != keywords.strip():
                await KnowledgeBaseService.update_article(
                    session=session, article=article, solution=solution, keywords=keywords
                )
                print(f"Updated article #{article.id}: {article.question[:60]}...")
            else:
                print(f"Unchanged: {question[:60]}...")


if __name__ == "__main__":
    asyncio.run(main())
