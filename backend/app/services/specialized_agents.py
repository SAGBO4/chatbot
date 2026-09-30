import re
import logging
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
import httpx

from app.config import settings
from app.models import KnowledgeArticle
from app.services.ai_assistant import AIAssistantService

logger = logging.getLogger(__name__)

# Stopwords and markers used for high-accuracy language detection between FR and EN
PURE_FRENCH_WORDS = {
    "le", "la", "les", "du", "des", "un", "une", "je", "tu", "il", "elle",
    "nous", "vous", "ils", "elles", "suis", "est", "sommes", "etes", "sont",
    "mon", "ma", "mes", "ton", "ta", "tes", "son", "sa", "ses", "notre",
    "votre", "leur", "leurs", "ce", "cet", "cette", "ces", "dans", "pour",
    "par", "sur", "avec", "sans", "sous", "vers", "pas", "ne", "qui", "que",
    "quoi", "dont", "ou", "mais", "oui", "non", "au", "aux", "très", "plus",
    "aussi", "comme", "tout", "tous", "toutes", "si", "vos", "proposons",
    "choisissez", "noter", "termes", "utilisés", "désignent", "permet", "cas",
    "prélève", "associe", "restaurer", "complètement", "restent", "toutes",
    "pouvez", "facilement", "créez", "lorsque", "connecte"
}

PURE_ENGLISH_WORDS = {
    "the", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "to", "at", "with", "about",
    "into", "through", "during", "before", "after", "above", "below", "from",
    "up", "down", "off", "over", "under", "then", "here", "there", "when",
    "where", "why", "how", "all", "any", "both", "each", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own",
    "same", "so", "than", "too", "very", "can", "will", "just", "should",
    "now", "my", "your", "his", "her", "its", "our", "their", "what",
    "which", "who", "whom", "this", "that", "you", "they", "we", "he",
    "she", "it", "yes", "please", "out", "by", "on", "offer", "refer",
    "charges", "partners", "sure", "feature", "unfortunately", "drop",
    "restoring", "completely", "keeps", "technologies", "send", "receive",
    "partnered", "create", "favorites", "auto", "convenient", "uses",
    "saving", "fees"
}


def detect_text_language(text: str) -> str:
    """Detect whether a snippet is French ('fr') or English ('en')."""
    words = set(re.findall(r"\b\w{2,}\b", text.lower()))
    fr_accents = len(re.findall(r"[éèêëàâôûùçîï«»]", text.lower()))
    fr_score = len(words & PURE_FRENCH_WORDS) + fr_accents * 2
    en_score = len(words & PURE_ENGLISH_WORDS)

    if fr_score > en_score:
        return "fr"
    elif en_score > fr_score:
        return "en"
    return "unknown"


def extract_monolingual_solution(text: str, target_lang: str) -> str:
    """
    Extracts strictly the text in target_lang ('fr' or 'en') from a knowledge base solution.
    If the text is bilingual (e.g. French section on top, English section below),
    it isolates and returns ONLY the section in target_lang.
    If the text is not bilingual, returns the text as is.
    """
    cleaned = text.strip()
    if not cleaned:
        return cleaned

    # 1. Try splitting by double newline (\n\n) - paragraphs
    paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
    if len(paragraphs) >= 2:
        langs = [detect_text_language(p) for p in paragraphs]
        if "fr" in langs and "en" in langs:
            matching = [p for p, lg in zip(paragraphs, langs) if lg == target_lang]
            if matching:
                return "\n\n".join(matching)

    # 2. Try splitting by single newline (\n) - lines
    lines = [line.strip() for line in cleaned.split("\n") if line.strip()]
    if len(lines) >= 2:
        langs = [detect_text_language(line) for line in lines]
        if "fr" in langs and "en" in langs:
            matching = [line for line, lg in zip(lines, langs) if lg == target_lang]
            if matching:
                return "\n".join(matching)

    return cleaned


class BaseSupportAgent(ABC):
    """Abstract base class for a language-specialized support agent."""

    language: str
    name: str

    def extract_solution(self, text: str) -> str:
        """Extracts only the content corresponding to this agent's specialty language."""
        return extract_monolingual_solution(text, self.language)

    @abstractmethod
    def build_system_prompt(self) -> str:
        """Returns the system prompt enforcing strict monolingual output and tone."""
        pass

    @abstractmethod
    def build_user_prompt(
        self, query: str, retrieved_articles: List[Tuple[KnowledgeArticle, float]]
    ) -> str:
        """Builds the user prompt containing extracted article contexts in the target language."""
        pass

    async def generate_ai_answer(
        self,
        query: str,
        retrieved_articles: List[Tuple[KnowledgeArticle, float]],
        client: Optional[httpx.AsyncClient] = None,
    ) -> Optional[str]:
        """Synthesizes an answer using the LLM with this agent's specialized prompts."""
        system_prompt = self.build_system_prompt()
        user_prompt = self.build_user_prompt(query, retrieved_articles)

        return await AIAssistantService.generate_answer(
            query=query,
            retrieved_articles=retrieved_articles,
            client=client,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    async def answer_query(
        self,
        query: str,
        retrieved_articles: List[Tuple[KnowledgeArticle, float]],
        client: Optional[httpx.AsyncClient] = None,
    ) -> str:
        """
        Executes the agent's complete resolution pipeline:
        1. Attempts LLM synthesis with specialized language prompt if AI is enabled.
        2. Falls back to extracting ONLY this agent's language from the best article's solution.
        """
        if not retrieved_articles:
            return ""

        best_article = retrieved_articles[0][0]

        # 1. AI synthesis if enabled
        if settings.AI_ENABLED and settings.AI_API_KEY:
            ai_answer = await self.generate_ai_answer(query, retrieved_articles, client=client)
            if ai_answer:
                return ai_answer

        # 2. Fallback to monolingual extraction
        return self.extract_solution(best_article.solution)


class FrenchSupportAgent(BaseSupportAgent):
    """
    Specialized agent for French-speaking users.
    Ensures that support responses are delivered EXCLUSIVELY in French,
    never mixing English text or duplicate bilingual translations.
    """

    language = "fr"
    name = "FrenchSupportAgent"

    def build_system_prompt(self) -> str:
        return (
            "Tu es un agent d'assistance technique spécialisé pour Stack Wallet, communiquant exclusivement en langue française. "
            "Tu fournis des instructions techniques directes, concises, objectives et vérifiées étape par étape, en te basant UNIQUEMENT sur la documentation fournie. "
            "Tu ne dois JAMAIS inclure de texte en anglais, ni traduire en anglais, ni fournir de réponse bilingue. "
            "Ne dis jamais 'Je', 'à mon avis', 'en tant qu'assistant'. Pas de bavardage ni de formule de politesse inutile. "
            "Réponds UNIQUEMENT et EXCLUSIVEMENT en français."
        )

    def build_user_prompt(
        self, query: str, retrieved_articles: List[Tuple[KnowledgeArticle, float]]
    ) -> str:
        context_snippets = []
        for idx, (art, _) in enumerate(retrieved_articles[:AIAssistantService.CONTEXT_ARTICLES], start=1):
            fr_sol = self.extract_solution(art.solution)
            context_snippets.append(f"[{idx}] Question: {art.question}\nSolution: {fr_sol}")
        context_str = "\n\n".join(context_snippets)

        return (
            "Tu es un agent de support technique officiel pour Stack Wallet.\n"
            "Règles impératives :\n"
            "1. Réponds à la question de l'utilisateur en utilisant UNIQUEMENT les solutions documentées ci-dessous.\n"
            "2. Rédige ta réponse STRICTEMENT et INTÉGRALEMENT en français. N'inclus AUCUN mot ni paragraphe en anglais.\n"
            "3. Ne donne aucune formule de politesse, ni introduction, ni conclusion. Donne uniquement les instructions techniques vérifiées étape par étape.\n\n"
            f"--- CONTEXTE TECHNIQUE OFFICIEL ---\n{context_str}\n\n"
            f"--- QUESTION DE L'UTILISATEUR ---\n{query}\n\n"
            "--- RÉSOLUTION TECHNIQUE EN FRANÇAIS ---"
        )


class EnglishSupportAgent(BaseSupportAgent):
    """
    Specialized agent for English-speaking users.
    Ensures that support responses are delivered EXCLUSIVELY in English,
    never mixing French text or duplicate bilingual translations.
    """

    language = "en"
    name = "EnglishSupportAgent"

    def build_system_prompt(self) -> str:
        return (
            "You are a specialized technical support agent for Stack Wallet, communicating exclusively in English. "
            "You provide direct, concise, objective, verified technical instructions step-by-step, based ONLY on the provided documentation. "
            "You must NEVER include French text, nor translate into French, nor provide a bilingual response. "
            "Never say 'I', 'in my opinion', 'as an assistant'. Do NOT use conversational filler. "
            "Answer ONLY and EXCLUSIVELY in English."
        )

    def build_user_prompt(
        self, query: str, retrieved_articles: List[Tuple[KnowledgeArticle, float]]
    ) -> str:
        context_snippets = []
        for idx, (art, _) in enumerate(retrieved_articles[:AIAssistantService.CONTEXT_ARTICLES], start=1):
            en_sol = self.extract_solution(art.solution)
            context_snippets.append(f"[{idx}] Question: {art.question}\nSolution: {en_sol}")
        context_str = "\n\n".join(context_snippets)

        return (
            "You are an official technical support agent for Stack Wallet.\n"
            "Mandatory rules:\n"
            "1. Answer the user's question using ONLY the documented solutions below.\n"
            "2. Provide your response STRICTLY and ENTIRELY in English. Do NOT include ANY French words or paragraphs.\n"
            "3. No conversational filler, greetings, or conclusions. Provide only direct, objective, verified technical instructions step-by-step.\n\n"
            f"--- OFFICIAL TECHNICAL CONTEXT ---\n{context_str}\n\n"
            f"--- USER QUESTION ---\n{query}\n\n"
            "--- TECHNICAL RESOLUTION IN ENGLISH ---"
        )


class AgentCoordinator:
    """Coordinates and routes support queries to language-specialized agents."""

    _agents = {
        "fr": FrenchSupportAgent(),
        "en": EnglishSupportAgent(),
    }

    @classmethod
    def get_agent(cls, language: Optional[str] = None) -> BaseSupportAgent:
        """Returns the specialized agent for the given language (defaults to French)."""
        lang = (language or "fr").strip().lower()
        return cls._agents.get(lang, cls._agents["fr"])

    @classmethod
    async def answer_query(
        cls,
        query: str,
        retrieved_articles: List[Tuple[KnowledgeArticle, float]],
        language: Optional[str] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> str:
        """Directs the query and context to the specialized agent according to language configuration."""
        agent = cls.get_agent(language)
        return await agent.answer_query(query, retrieved_articles, client=client)
