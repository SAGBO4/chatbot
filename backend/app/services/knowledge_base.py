import re
import math
import asyncio
from collections import Counter
from typing import List, Tuple, Optional, Set
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import KnowledgeArticle

FRENCH_STOPWORDS = {
    "le", "la", "les", "de", "du", "des", "un", "une", "je", "tu", "il", "elle",
    "nous", "vous", "ils", "elles", "on", "ai", "as", "a", "avons", "avez", "ont",
    "suis", "es", "est", "sommes", "etes", "sont", "mon", "ma", "mes", "ton", "ta",
    "tes", "son", "sa", "ses", "notre", "votre", "leur", "leurs", "ce", "cet", "cette",
    "ces", "quand", "comment", "pourquoi", "qui", "que", "quoi", "dont", "ou", "en",
    "et", "mais", "dans", "pour", "par", "sur", "avec", "sans", "sous", "vers", "tente",
    "faire", "pas", "du", "tout", "ne", "j", "d", "l", "m", "t", "s", "c", "n", "y"
}

ENGLISH_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "to", "at", "in", "for",
    "on", "by", "with", "about", "against", "between", "into", "through",
    "during", "before", "after", "above", "below", "from", "up", "down",
    "of", "off", "over", "under", "again", "further", "then", "once",
    "here", "there", "when", "where", "why", "how", "all", "any", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "can",
    "will", "just", "should", "now", "my", "your", "his", "her",
    "its", "our", "their", "what", "which", "who", "whom", "this", "that"
}

BILINGUAL_STOPWORDS = FRENCH_STOPWORDS | ENGLISH_STOPWORDS


def tokenize(text: str, remove_stopwords: bool = True) -> List[str]:
    """Tokenize text into lowercased words, optionally filtering bilingual stopwords."""
    text = text.lower()
    words = re.findall(r"\b\w{2,}\b", text)
    if remove_stopwords:
        filtered = [w for w in words if w not in BILINGUAL_STOPWORDS]
        return filtered if filtered else words
    return words


def compute_tf_vector(tokens: List[str]) -> Counter:
    """Count how many times each token occurs (raw term frequencies, not normalized)."""
    return Counter(tokens)


def token_similarity(vec1: Counter, vec2: Counter) -> float:
    """Share of `vec1`'s tokens found in `vec2`: an exact match counts 1, a prefix or substring match 0.85."""
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
    """Cosine similarity of character n-grams (fuzzy match); the length ratio when one string contains the other."""
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
    """All distinct non-stopword tokens of `text`, sorted, as a comma-separated string."""
    tokens = tokenize(text, remove_stopwords=True)
    return ", ".join(sorted(set(tokens)))


class KnowledgeBaseService:
    """Stores knowledge base articles and finds the best matches for a question (no embeddings: pure lexical scoring)."""

    @staticmethod
    async def add_article(
        session: AsyncSession,
        question: str,
        solution: str,
        keywords: Optional[str] = None,
        source_ticket_id: Optional[int] = None,
        auto_commit: bool = True,
    ) -> KnowledgeArticle:
        """
        Add an article, or update the one already linked to `source_ticket_id` (one article per ticket).

        Keywords default to the question's tokens. With `auto_commit=False` it only flushes.
        """
        computed_keywords = keywords or extract_keywords_from_text(question)

        if source_ticket_id is not None:
            existing_stmt = select(KnowledgeArticle).where(KnowledgeArticle.source_ticket_id == source_ticket_id)
            existing_res = await session.execute(existing_stmt)
            existing = existing_res.scalars().first()
            if existing:
                existing.question = question.strip()
                existing.solution = solution.strip()
                if computed_keywords:
                    existing.keywords = computed_keywords.strip()
                if auto_commit:
                    await session.commit()
                    await session.refresh(existing)
                else:
                    await session.flush()
                return existing

        article = KnowledgeArticle(
            question=question.strip(),
            solution=solution.strip(),
            keywords=computed_keywords.strip() if computed_keywords else None,
            source_ticket_id=source_ticket_id,
        )
        session.add(article)
        if auto_commit:
            await session.commit()
            await session.refresh(article)
        else:
            await session.flush()
        return article

    @staticmethod
    async def get_all_articles(
        session: AsyncSession, limit: int = 50, offset: int = 0
    ) -> List[KnowledgeArticle]:
        result = await session.execute(
            select(KnowledgeArticle)
            .order_by(KnowledgeArticle.id.desc())
            .limit(limit)
            .offset(offset)
        )
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
        """
        Best matches for `query` as `(article, score)` pairs, highest score first, above `threshold`.

        Up to 200 candidate rows are pre-filtered in SQL (LIKE on question and keywords for the first
        12 tokens, then a character-trigram retry if nothing matches) and scored in Python.
        """
        query_text = query.strip()
        if not query_text:
            return []

        query_tokens = tokenize(query_text, remove_stopwords=True)
        if not query_tokens:
            return []

        query_vec = compute_tf_vector(query_tokens)

        stmt = select(KnowledgeArticle)
        conditions = []
        # Only the first 12 tokens, so a long query cannot explode the SQL clause
        for token in query_tokens[:12]:
            term = f"%{token}%"
            conditions.append(KnowledgeArticle.question.ilike(term))
            conditions.append(KnowledgeArticle.keywords.ilike(term))
            if len(token) >= 4:
                prefix_term = f"%{token[:4]}%"
                conditions.append(KnowledgeArticle.question.ilike(prefix_term))
                conditions.append(KnowledgeArticle.keywords.ilike(prefix_term))
        stmt = stmt.where(or_(*conditions)).limit(200)

        result = await session.execute(stmt)
        articles = list(result.scalars().all())

        if not articles:
            # Nothing matched (typos, variants): retry with character trigrams of the first 6 tokens.
            trigrams = set()
            for token in query_tokens[:6]:
                if len(token) >= 3:
                    for i in range(len(token) - 2):
                        trigrams.add(token[i : i + 3])

            fallback_conditions = []
            for tri in list(trigrams)[:15]:
                term = f"%{tri}%"
                fallback_conditions.append(KnowledgeArticle.question.ilike(term))
                fallback_conditions.append(KnowledgeArticle.keywords.ilike(term))

            if fallback_conditions:
                fallback_stmt = select(KnowledgeArticle).where(or_(*fallback_conditions)).limit(200)
            else:
                fallback_stmt = select(KnowledgeArticle).order_by(KnowledgeArticle.id.desc()).limit(200)

            fallback_res = await session.execute(fallback_stmt)
            articles = list(fallback_res.scalars().all())
            if not articles:
                return []

        # CPU-bound scoring runs in a thread so it does not block the event loop
        return await asyncio.to_thread(
            cls._score_and_rank_articles,
            articles=articles,
            query_text=query_text,
            query_vec=query_vec,
            threshold=threshold,
            limit=limit,
        )

    @classmethod
    def _score_and_rank_articles(
        cls,
        articles: List[KnowledgeArticle],
        query_text: str,
        query_vec: Counter,
        threshold: float,
        limit: int,
    ) -> List[Tuple[KnowledgeArticle, float]]:
        """
        Score each article and keep those at or above `threshold`.

        score = min(1, 0.65 * token_similarity + 0.2 * char_ngram_similarity(query, question)
                       + keyword_bonus + exact_bonus)
        keyword_bonus: 0.2 per article keyword contained in the query, capped at 0.4.
        exact_bonus:   0.25 when the query and the question contain one another (query of 4+ chars).
        """
        scored: List[Tuple[KnowledgeArticle, float]] = []

        for article in articles:
            article_text = f"{article.question} {article.keywords or ''}"
            article_tokens = tokenize(article_text, remove_stopwords=True)
            article_vec = compute_tf_vector(article_tokens)

            tok_sim = token_similarity(query_vec, article_vec)

            char_sim = compute_char_ngram_similarity(query_text, article.question)

            kw_bonus = 0.0
            if article.keywords:
                raw_kws = [k.strip().lower() for k in article.keywords.split(",") if k.strip()]
                for kw in raw_kws:
                    if kw in query_text.lower():
                        kw_bonus += 0.2
            kw_bonus = min(0.4, kw_bonus)

            # Minimum length, or single common letters would match everything
            exact_bonus = 0.0
            if len(query_text) >= 4 and (
                query_text.lower() in article.question.lower() or article.question.lower() in query_text.lower()
            ):
                exact_bonus = 0.25

            final_score = min(1.0, (tok_sim * 0.65) + (char_sim * 0.2) + kw_bonus + exact_bonus)

            if final_score >= threshold:
                scored.append((article, round(final_score, 4)))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:limit]
