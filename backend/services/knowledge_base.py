import re
import math
from collections import Counter
from typing import List, Tuple, Optional, Set
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models import KnowledgeArticle

FRENCH_STOPWORDS = {
    "le", "la", "les", "de", "du", "des", "un", "une", "je", "tu", "il", "elle",
    "nous", "vous", "ils", "elles", "on", "ai", "as", "a", "avons", "avez", "ont",
    "suis", "es", "est", "sommes", "etes", "sont", "mon", "ma", "mes", "ton", "ta",
    "tes", "son", "sa", "ses", "notre", "votre", "leur", "leurs", "ce", "cet", "cette",
    "ces", "quand", "comment", "pourquoi", "qui", "que", "quoi", "dont", "ou", "en",
    "et", "mais", "dans", "pour", "par", "sur", "avec", "sans", "sous", "vers", "tente",
    "faire", "pas", "du", "tout", "ne", "j", "d", "l", "m", "t", "s", "c", "n", "y"
}


def tokenize(text: str, remove_stopwords: bool = True) -> List[str]:
    """Tokenize text into lowercased words, optionally filtering stopwords."""
    text = text.lower()
    words = re.findall(r"\b\w{2,}\b", text)
    if remove_stopwords:
        filtered = [w for w in words if w not in FRENCH_STOPWORDS]
        return filtered if filtered else words
    return words


def compute_tf_vector(tokens: List[str]) -> Counter:
    """Compute normalized term frequencies."""
    return Counter(tokens)


def token_similarity(vec1: Counter, vec2: Counter) -> float:
    """Compute token overlap similarity with prefix and stem matching."""
    if not vec1 or not vec2:
        return 0.0

    tokens1 = set(vec1.keys())
    tokens2 = set(vec2.keys())

    # Exact token intersection
    exact_matches = tokens1 & tokens2

    # Stem / prefix matching (e.g. 'export' and 'exporter', 'bloqué' and 'bloquer')
    prefix_matches: Set[str] = set()
    for t1 in tokens1 - exact_matches:
        for t2 in tokens2 - exact_matches:
            min_len = min(len(t1), len(t2))
            prefix_len = min(4, min_len)
            if (prefix_len >= 3 and t1[:prefix_len] == t2[:prefix_len]) or t1 in t2 or t2 in t1:
                prefix_matches.add(t1)
                break

    matched_count = len(exact_matches) + (0.85 * len(prefix_matches))
    total_query_tokens = len(tokens1)

    return min(1.0, matched_count / max(1, total_query_tokens))


def compute_char_ngram_similarity(s1: str, s2: str, n: int = 3) -> float:
    """Compute character n-gram similarity for fuzzy matching."""
    s1, s2 = s1.lower(), s2.lower()
    if not s1 or not s2:
        return 0.0
    if s1 in s2 or s2 in s1:
        return min(len(s1), len(s2)) / max(len(s1), len(s2))

    ngrams1 = Counter([s1[i:i + n] for i in range(len(s1) - n + 1)])
    ngrams2 = Counter([s2[i:i + n] for i in range(len(s2) - n + 1)])

    intersection = set(ngrams1.keys()) & set(ngrams2.keys())
    if not intersection:
        return 0.0

    dot = sum(ngrams1[x] * ngrams2[x] for x in intersection)
    mag1 = math.sqrt(sum(v ** 2 for v in ngrams1.values()))
    mag2 = math.sqrt(sum(v ** 2 for v in ngrams2.values()))

    return dot / (mag1 * mag2) if (mag1 and mag2) else 0.0


def extract_keywords_from_text(text: str) -> str:
    """Helper to extract top keywords from a sentence."""
    tokens = tokenize(text, remove_stopwords=True)
    return ", ".join(sorted(set(tokens)))


class KnowledgeBaseService:
    @staticmethod
    async def add_article(
        session: AsyncSession,
        question: str,
        solution: str,
        keywords: Optional[str] = None,
        source_ticket_id: Optional[int] = None,
    ) -> KnowledgeArticle:
        # If no keywords provided, automatically extract from the question
        computed_keywords = keywords or extract_keywords_from_text(question)

        article = KnowledgeArticle(
            question=question.strip(),
            solution=solution.strip(),
            keywords=computed_keywords.strip() if computed_keywords else None,
            source_ticket_id=source_ticket_id,
        )
        session.add(article)
        await session.commit()
        await session.refresh(article)
        return article

    @staticmethod
    async def get_all_articles(session: AsyncSession) -> List[KnowledgeArticle]:
        result = await session.execute(select(KnowledgeArticle))
        return list(result.scalars().all())

    @staticmethod
    async def get_article_by_question(session: AsyncSession, question: str) -> Optional[KnowledgeArticle]:
        result = await session.execute(
            select(KnowledgeArticle).where(KnowledgeArticle.question == question)
        )
        return result.scalars().first()

    @staticmethod
    async def update_article(
        session: AsyncSession,
        article: KnowledgeArticle,
        solution: Optional[str] = None,
        keywords: Optional[str] = None,
    ) -> KnowledgeArticle:
        if solution is not None:
            article.solution = solution.strip()
        if keywords is not None:
            article.keywords = keywords.strip()
        await session.commit()
        await session.refresh(article)
        return article

    @staticmethod
    async def delete_article(session: AsyncSession, article: KnowledgeArticle) -> None:
        await session.delete(article)
        await session.commit()

    @classmethod
    async def search(
        cls,
        session: AsyncSession,
        query: str,
        threshold: float = 0.3,
        limit: int = 5,
    ) -> List[Tuple[KnowledgeArticle, float]]:
        """Search knowledge base articles using combined lexical and semantic scoring."""
        query_text = query.strip()
        if not query_text:
            return []

        query_tokens = tokenize(query_text, remove_stopwords=True)
        query_vec = compute_tf_vector(query_tokens)

        stmt = select(KnowledgeArticle)
        if query_tokens:
            conditions = []
            for token in query_tokens:
                term = f"%{token}%"
                conditions.append(KnowledgeArticle.question.ilike(term))
                conditions.append(KnowledgeArticle.keywords.ilike(term))
            stmt = stmt.where(or_(*conditions))
            
        result = await session.execute(stmt)
        articles = list(result.scalars().all())

        if not articles:
            return []

        scored: List[Tuple[KnowledgeArticle, float]] = []

        for article in articles:
            article_text = f"{article.question} {article.keywords or ''}"
            article_tokens = tokenize(article_text, remove_stopwords=True)
            article_vec = compute_tf_vector(article_tokens)

            # Token / prefix similarity
            tok_sim = token_similarity(query_vec, article_vec)

            # Character ngram similarity
            char_sim = compute_char_ngram_similarity(query_text, article.question)

            # Keyword direct match bonus
            kw_bonus = 0.0
            if article.keywords:
                raw_kws = [k.strip().lower() for k in article.keywords.split(",") if k.strip()]
                for kw in raw_kws:
                    if kw in query_text.lower():
                        kw_bonus += 0.2
            kw_bonus = min(0.4, kw_bonus)

            # Substring / exact match bonus
            exact_bonus = 0.0
            if query_text.lower() in article.question.lower() or article.question.lower() in query_text.lower():
                exact_bonus = 0.25

            # Combined score capped at 1.0
            final_score = min(1.0, (tok_sim * 0.65) + (char_sim * 0.2) + kw_bonus + exact_bonus)

            if final_score >= threshold:
                scored.append((article, round(final_score, 4)))

        # Sort by score descending
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:limit]
