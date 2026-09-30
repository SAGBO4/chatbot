import pytest
from unittest.mock import AsyncMock
import httpx

from app.config import settings
from app.models import KnowledgeArticle
from app.services.knowledge_base import KnowledgeBaseService
from app.services.ai_assistant import AIAssistantService
from app.services.specialized_agents import (
    FrenchSupportAgent,
    EnglishSupportAgent,
    AgentCoordinator,
    detect_text_language,
    extract_monolingual_solution,
)


@pytest.fixture
def bilingual_article():
    return KnowledgeArticle(
        question="Où puis-je obtenir de l'aide / support Stack Wallet ? / Where can I get Stack Wallet support?",
        solution=(
            "Nous proposons du support sur plusieurs canaux. Choisissez celui qui vous convient le mieux :\n"
            "• Email : support@stackwallet.com\n"
            "• Telegram : @stackwallet\n"
            "• Discord : Stack Wallet\n\n"
            "We offer support on a variety of platforms. Please choose the one below that is most convenient for you:\n"
            "• Email: support@stackwallet.com\n"
            "• Telegram: @stackwallet\n"
            "• Discord: Stack Wallet"
        ),
        keywords="support, aide, help, contact, email",
    )


@pytest.fixture
def inline_bilingual_article():
    return KnowledgeArticle(
        question="Stack Wallet est-il open-source ? / Is Stack Wallet open-source?",
        solution=(
            "Oui, complètement : pas partiellement, pas majoritairement, entièrement open-source. Un code entièrement ouvert offre sécurité, robustesse et stabilité.\n"
            "Yes, completely — not partially, not mostly, fully open-source. A completely open-source codebase offers security, power, and stability."
        ),
        keywords="open source, code source, security, securite",
    )


def test_detect_text_language():
    fr_sample = "Nous proposons du support technique complet pour votre portefeuille."
    en_sample = "We offer comprehensive technical support for your cryptocurrency wallet."

    assert detect_text_language(fr_sample) == "fr"
    assert detect_text_language(en_sample) == "en"


def test_extract_monolingual_solution_multiline(bilingual_article):
    fr_res = extract_monolingual_solution(bilingual_article.solution, "fr")
    en_res = extract_monolingual_solution(bilingual_article.solution, "en")

    assert "Nous proposons du support" in fr_res
    assert "We offer support" not in fr_res

    assert "We offer support" in en_res
    assert "Nous proposons du support" not in en_res


def test_extract_monolingual_solution_inline(inline_bilingual_article):
    fr_res = extract_monolingual_solution(inline_bilingual_article.solution, "fr")
    en_res = extract_monolingual_solution(inline_bilingual_article.solution, "en")

    assert "Oui, complètement" in fr_res
    assert "Yes, completely" not in fr_res

    assert "Yes, completely" in en_res
    assert "Oui, complètement" not in en_res


def test_extract_monolingual_solution_pure_text():
    pure_fr = "Définir HTTPS_PROXY dans votre environnement."
    pure_en = "Set HTTPS_PROXY in your environment."

    assert extract_monolingual_solution(pure_fr, "fr") == pure_fr
    assert extract_monolingual_solution(pure_en, "en") == pure_en


def test_agent_coordinator_resolves_specialized_agents():
    fr_agent = AgentCoordinator.get_agent("fr")
    en_agent = AgentCoordinator.get_agent("en")
    fallback_agent = AgentCoordinator.get_agent("unknown")

    assert isinstance(fr_agent, FrenchSupportAgent)
    assert fr_agent.language == "fr"

    assert isinstance(en_agent, EnglishSupportAgent)
    assert en_agent.language == "en"

    # Unknown language safely falls back to default French agent
    assert isinstance(fallback_agent, FrenchSupportAgent)


@pytest.mark.asyncio
async def test_specialized_agents_fallback_extraction_without_ai(bilingual_article, monkeypatch):
    monkeypatch.setattr(settings, "AI_ENABLED", False)
    fr_agent = FrenchSupportAgent()
    en_agent = EnglishSupportAgent()

    matches = [(bilingual_article, 0.95)]

    fr_answer = await fr_agent.answer_query("Comment obtenir du support ?", matches)
    en_answer = await en_agent.answer_query("How to get support?", matches)

    assert "Nous proposons du support" in fr_answer
    assert "We offer support" not in fr_answer

    assert "We offer support" in en_answer
    assert "Nous proposons du support" not in en_answer


@pytest.mark.asyncio
async def test_specialized_agents_with_ai_enabled(inline_bilingual_article, monkeypatch):
    monkeypatch.setattr(settings, "AI_ENABLED", True)
    monkeypatch.setattr(settings, "AI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "AI_PROVIDER", "openai")

    fr_agent = FrenchSupportAgent()
    en_agent = EnglishSupportAgent()

    # Mock client to inspect the prompts sent by each specialized agent
    captured_calls = []

    async def mock_post(url, headers=None, json=None, **kwargs):
        captured_calls.append(json)
        # Return simulated single-language answers
        sys_content = json["messages"][0]["content"]
        if "française" in sys_content:
            return httpx.Response(200, json={"choices": [{"message": {"content": "Oui, Stack Wallet est 100% open-source."}}]})
        else:
            return httpx.Response(200, json={"choices": [{"message": {"content": "Yes, Stack Wallet is completely open-source."}}]})

    mock_client = AsyncMock()
    mock_client.post = mock_post
    AIAssistantService.set_shared_client(mock_client)

    try:
        matches = [(inline_bilingual_article, 0.95)]

        fr_answer = await fr_agent.answer_query("Stack est-il open source ?", matches)
        assert fr_answer == "Oui, Stack Wallet est 100% open-source."
        fr_payload = captured_calls[0]
        assert "exclusivement en langue française" in fr_payload["messages"][0]["content"]
        assert "RÉSOLUTION TECHNIQUE EN FRANÇAIS" in fr_payload["messages"][1]["content"]

        en_answer = await en_agent.answer_query("Is Stack open source?", matches)
        assert en_answer == "Yes, Stack Wallet is completely open-source."
        en_payload = captured_calls[1]
        assert "exclusively in English" in en_payload["messages"][0]["content"]
        assert "TECHNICAL RESOLUTION IN ENGLISH" in en_payload["messages"][1]["content"]

    finally:
        AIAssistantService.set_shared_client(None)


@pytest.mark.asyncio
async def test_query_endpoint_returns_monolingual_french_by_default(app_test_env, bilingual_article):
    client, session_maker, _ = app_test_env

    async with session_maker() as session:
        await session.merge(bilingual_article)
        await session.commit()

    response = await client.post(
        "/api/query",
        json={"query": "Où puis-je obtenir de l'aide ?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["found"] is True

    # MUST be strictly French, no English block!
    assert "Nous proposons du support sur plusieurs canaux" in data["answer"]
    assert "We offer support on a variety of platforms" not in data["answer"]


@pytest.mark.asyncio
async def test_query_endpoint_returns_monolingual_english_when_configured(app_test_env, bilingual_article):
    client, session_maker, _ = app_test_env

    async with session_maker() as session:
        await session.merge(bilingual_article)
        await session.commit()

    # Change configuration to English
    resp_lang = await client.put("/api/admin/settings/language", json={"value": "en"})
    assert resp_lang.status_code == 200

    response = await client.post(
        "/api/query",
        json={"query": "Where can I get Stack Wallet support?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["found"] is True

    # MUST be strictly English, no French block!
    assert "We offer support on a variety of platforms" in data["answer"]
    assert "Nous proposons du support sur plusieurs canaux" not in data["answer"]


@pytest.mark.asyncio
async def test_query_endpoint_respects_explicit_payload_language(app_test_env, bilingual_article):
    client, session_maker, _ = app_test_env

    async with session_maker() as session:
        await session.merge(bilingual_article)
        await session.commit()

    # Bot setting is French by default, but request explicitly asks for English
    response_en = await client.post(
        "/api/query",
        json={"query": "Where can I get Stack Wallet support?", "language": "en"},
    )
    assert response_en.status_code == 200
    data_en = response_en.json()
    assert "We offer support on a variety of platforms" in data_en["answer"]
    assert "Nous proposons du support" not in data_en["answer"]

    # Now request explicitly asks for French
    response_fr = await client.post(
        "/api/query",
        json={"query": "Where can I get Stack Wallet support?", "language": "fr"},
    )
    assert response_fr.status_code == 200
    data_fr = response_fr.json()
    assert "Nous proposons du support" in data_fr["answer"]
    assert "We offer support" not in data_fr["answer"]


def test_specialized_agents_system_and_user_prompts_enforce_strict_monolingual(bilingual_article):
    fr_agent = FrenchSupportAgent()
    en_agent = EnglishSupportAgent()

    fr_sys = fr_agent.build_system_prompt()
    assert "exclusivement en langue française" in fr_sys
    assert "JAMAIS inclure de texte en anglais" in fr_sys
    assert "bilingue" in fr_sys

    fr_user = fr_agent.build_user_prompt("Question test", [(bilingual_article, 0.9)])
    assert "STRICTEMENT et INTÉGRALEMENT en français" in fr_user
    assert "AUCUN mot ni paragraphe en anglais" in fr_user
    assert "RÉSOLUTION TECHNIQUE EN FRANÇAIS" in fr_user

    en_sys = en_agent.build_system_prompt()
    assert "exclusively in English" in en_sys
    assert "NEVER include French text" in en_sys
    assert "bilingual" in en_sys

    en_user = en_agent.build_user_prompt("Question test", [(bilingual_article, 0.9)])
    assert "STRICTLY and ENTIRELY in English" in en_user
    assert "Do NOT include ANY French words or paragraphs" in en_user
    assert "TECHNICAL RESOLUTION IN ENGLISH" in en_user


def test_all_22_seed_knowledge_articles_monolingual_extraction():
    import json
    from pathlib import Path

    seed_path = Path(__file__).parent.parent / "scripts" / "knowledge_base_seed.json"
    assert seed_path.exists(), f"Seed file not found at {seed_path}"

    with open(seed_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    articles = data.get("articles", [])
    assert len(articles) == 22, f"Expected 22 articles, found {len(articles)}"

    fr_agent = FrenchSupportAgent()
    en_agent = EnglishSupportAgent()

    for idx, art in enumerate(articles, 1):
        sol = art["solution"]
        fr_extract = fr_agent.extract_solution(sol)
        en_extract = en_agent.extract_solution(sol)

        # Must not be empty
        assert fr_extract.strip(), f"Article #{idx} FR extraction is empty"
        assert en_extract.strip(), f"Article #{idx} EN extraction is empty"

        # Must be different
        assert fr_extract != en_extract, f"Article #{idx} FR and EN extractions are identical"

        # Language detection must match target
        assert detect_text_language(fr_extract) == "fr", f"Article #{idx} FR extract was not detected as 'fr'"
        assert detect_text_language(en_extract) == "en", f"Article #{idx} EN extract was not detected as 'en'"

        # Verify no cross-language leakage
        assert not any(phrase in fr_extract for phrase in [
            "We offer", "Please choose", "WRITE IT DOWN", "We do not", "We sure do",
            "Unfortunately", "Drop us a line", "If the wallet", "keeps all private keys",
            "All privacy technologies", "You can send, receive", "We've partnered",
            "Back up your", "Create multiple", "With many wallets", "Auto connect",
            "Smart sync", "Most coins we support", "saving you on fees",
            "Mimblewimble coins utilize"
        ]), f"Article #{idx} has English leakage in FR extract: {fr_extract}"

        assert not any(phrase in en_extract for phrase in [
            "Nous proposons", "Choisissez celui", "NOTEZ-LA PAR ÉCRIT", "Stack Wallet prélève",
            "Oui ! Pensez", "Malheureusement non", "Contactez-nous", "Si la phrase",
            "vos clés privées restent", "Toutes les technologies", "Vous pouvez envoyer",
            "Stack Wallet s'est", "Vous pouvez sauvegarder", "Créez plusieurs adresses",
            "Lorsque vous avez", "se connecte automatiquement", "Le smart sync vous",
            "la plupart des coins", "permet de réduire les frais", "Les coins basés"
        ]), f"Article #{idx} has French leakage in EN extract: {en_extract}"


def test_complex_bullet_list_article_monolingual_extraction():
    import json
    from pathlib import Path

    seed_path = Path(__file__).parent.parent / "scripts" / "knowledge_base_seed.json"
    with open(seed_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Article 1 is the 8-bullet-point contact channels article
    art1_sol = data["articles"][0]["solution"]

    fr_sol = extract_monolingual_solution(art1_sol, "fr")
    en_sol = extract_monolingual_solution(art1_sol, "en")

    # French bullet checks
    assert "Nous proposons du support sur plusieurs canaux." in fr_sol
    assert "• Email : support@stackwallet.com" in fr_sol
    assert "• Telegram : @stackwallet" in fr_sol
    assert "• Discord : Stack Wallet" in fr_sol
    assert "• Mastodon : @stackwallet" in fr_sol
    assert "We offer support" not in fr_sol
    assert "most convenient for you" not in fr_sol

    # English bullet checks
    assert "We offer support on a variety of platforms." in en_sol
    assert "• Email: support@stackwallet.com" in en_sol
    assert "• Telegram: @stackwallet" in en_sol
    assert "• Discord: Stack Wallet" in en_sol
    assert "• Mastodon: @stackwallet" in en_sol
    assert "Nous proposons du support" not in en_sol
    assert "convient le mieux" not in en_sol


@pytest.mark.asyncio
async def test_orchestrator_edge_cases_monolingual(app_test_env):
    from app.services.query_orchestrator import QueryOrchestrator
    from app.services.bot_settings_service import BotSettingsService
    from app.i18n import t

    _, session_maker, _ = app_test_env

    async with session_maker() as session:
        # 1. Empty query with explicit "fr"
        res_fr_empty = await QueryOrchestrator.process_query(session, query="", language="fr")
        assert res_fr_empty.found is False
        assert res_fr_empty.answer == t("query_empty", "fr")
        assert detect_text_language(res_fr_empty.answer) == "fr"

        # 2. Empty query with explicit "en"
        res_en_empty = await QueryOrchestrator.process_query(session, query="   ", language="en")
        assert res_en_empty.found is False
        assert res_en_empty.answer == t("query_empty", "en")
        assert detect_text_language(res_en_empty.answer) == "en"

        # 3. No match query with explicit "fr"
        res_fr_nomatch = await QueryOrchestrator.process_query(
            session, query="xyzabc non-existent astronomical constellation 12345", language="fr"
        )
        assert res_fr_nomatch.found is False
        assert res_fr_nomatch.answer == t("query_no_match", "fr")
        assert "équipe support" in res_fr_nomatch.answer

        # 4. No match query with explicit "en"
        res_en_nomatch = await QueryOrchestrator.process_query(
            session, query="xyzabc non-existent astronomical constellation 12345", language="en"
        )
        assert res_en_nomatch.found is False
        assert res_en_nomatch.answer == t("query_no_match", "en")
        assert "support team" in res_en_nomatch.answer

        # 5. Respect configured language when payload language is None
        await BotSettingsService.set_language(session, "en")
        res_conf_en = await QueryOrchestrator.process_query(session, query="")
        assert res_conf_en.answer == t("query_empty", "en")

        await BotSettingsService.set_language(session, "fr")
        res_conf_fr = await QueryOrchestrator.process_query(session, query="")
        assert res_conf_fr.answer == t("query_empty", "fr")


def test_real_chatbot_db_seed_articles_monolingual_extraction():
    import sqlite3
    from pathlib import Path

    db_path = Path(__file__).parent.parent / "data" / "chatbot.db"
    if not db_path.exists():
        pytest.skip(f"Database file not found at {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, question, solution FROM knowledge_articles WHERE id BETWEEN 2 AND 24")
    rows = cursor.fetchall()
    conn.close()

    assert len(rows) == 22, f"Expected 22 seed articles in DB, got {len(rows)}"

    fr_agent = FrenchSupportAgent()
    en_agent = EnglishSupportAgent()

    for art_id, question, solution in rows:
        fr_extract = fr_agent.extract_solution(solution)
        en_extract = en_agent.extract_solution(solution)

        assert fr_extract.strip(), f"DB Article #{art_id} FR extraction is empty"
        assert en_extract.strip(), f"DB Article #{art_id} EN extraction is empty"
        assert fr_extract != en_extract, f"DB Article #{art_id} extractions are identical"

        assert detect_text_language(fr_extract) == "fr", f"DB Article #{art_id} not detected as FR"
        assert detect_text_language(en_extract) == "en", f"DB Article #{art_id} not detected as EN"


def test_detect_text_language_edge_cases():
    assert detect_text_language(None) == "unknown"
    assert detect_text_language("") == "unknown"
    assert detect_text_language("   ") == "unknown"
    assert detect_text_language("123456 !!! ???") == "unknown"
    assert detect_text_language(12345) == "unknown"


def test_extract_monolingual_solution_edge_cases():
    assert extract_monolingual_solution(None, "fr") == ""
    assert extract_monolingual_solution("", "en") == ""
    assert extract_monolingual_solution("   ", "fr") == ""
    assert extract_monolingual_solution(12345, "fr") == ""
    assert extract_monolingual_solution("Text without bilingual content", None) == "Text without bilingual content"
    assert extract_monolingual_solution("Text without bilingual content", "invalid_lang") == "Text without bilingual content"


def test_agent_coordinator_edge_cases():
    assert isinstance(AgentCoordinator.get_agent(None), FrenchSupportAgent)
    assert isinstance(AgentCoordinator.get_agent(""), FrenchSupportAgent)
    assert isinstance(AgentCoordinator.get_agent("   "), FrenchSupportAgent)
    assert isinstance(AgentCoordinator.get_agent(12345), FrenchSupportAgent)
    assert isinstance(AgentCoordinator.get_agent("FR"), FrenchSupportAgent)
    assert isinstance(AgentCoordinator.get_agent("EN"), EnglishSupportAgent)
    assert isinstance(AgentCoordinator.get_agent("es"), FrenchSupportAgent)


@pytest.mark.asyncio
async def test_specialized_agent_answer_query_empty_matches():
    fr_agent = FrenchSupportAgent()
    en_agent = EnglishSupportAgent()

    assert await fr_agent.answer_query("test", []) == ""
    assert await en_agent.answer_query("test", []) == ""
    assert await fr_agent.answer_query("test", [(None, 0.9)]) == ""


@pytest.mark.asyncio
async def test_specialized_agent_answer_query_with_none_solution():
    fr_agent = FrenchSupportAgent()
    art = KnowledgeArticle(question="Test question", solution="")
    art.solution = None
    res = await fr_agent.answer_query("Test", [(art, 0.95)])
    assert res == ""


@pytest.mark.asyncio
async def test_orchestrator_query_none_and_case_insensitive_language(app_test_env):
    from app.services.query_orchestrator import QueryOrchestrator
    from app.i18n import t

    _, session_maker, _ = app_test_env

    async with session_maker() as session:
        # 1. query is None
        res_none = await QueryOrchestrator.process_query(session, query=None, language="FR")
        assert res_none.found is False
        assert res_none.answer == t("query_empty", "fr")
        assert res_none.query == ""

        # 2. uppercase language 'EN'
        res_upper_en = await QueryOrchestrator.process_query(session, query="", language="EN")
        assert res_upper_en.found is False
        assert res_upper_en.answer == t("query_empty", "en")

        # 3. language with whitespace ' en '
        res_ws_en = await QueryOrchestrator.process_query(session, query="", language="  en  ")
        assert res_ws_en.found is False
        assert res_ws_en.answer == t("query_empty", "en")
