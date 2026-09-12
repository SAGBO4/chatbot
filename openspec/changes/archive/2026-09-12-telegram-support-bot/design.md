## Context

See `proposal.md` for background and motivation. The system implements a full-lifecycle support automation architecture on Telegram with a FastAPI backend, a dual-layer Knowledge Base (lexical + vector search), an optional AI/LLM generator, and a human support loop running directly inside a dedicated Telegram Support Group.

## Goals / Non-Goals

**Goals:**
- Provide a clean, modular Python architecture separating the Telegram Bot, Backend API, Knowledge Base, and Ticketing logic.
- Support hybrid / autonomous operation: operate in pure Knowledge Base search mode when AI is disabled, or context-grounded RAG mode when AI is enabled.
- Seamless end-user experience on Telegram with instant answer delivery and interactive inline confirmation ("Problème résolu ? OUI / NON").
- Zero-friction support workflow: support agents receive ticket notifications directly in a Telegram group and resolve tickets by simply replying to the notification message.
- Automatic continuous learning: agent solutions are ingested into the Knowledge Base upon ticket resolution so identical questions are resolved automatically in the future.

**Non-Goals:**
- External web portal for ticketing or complex multi-tier SLA enterprise tooling (all agent interactions take place in Telegram).
- Audio/voice note transcription or image processing in initial scope (text-based inquiries first).
- Complex multi-agent debate frameworks (keep retrieval and generation fast, deterministic, and cost-effective).

## Decisions

### Decision 1: Backend Framework — FastAPI
- **Choice**: FastAPI (Python 3.11+) with Pydantic v2 and SQLAlchemy / aiosqlite.
- **Rationale**: Asynchronous native support matching Telegram bot event loops, automatic OpenAPI documentation, clean dependency injection, and high throughput.
- **Alternatives considered**: Flask/Django (more boilerplate, less native async support).

### Decision 2: Telegram Bot Framework — aiogram 3.x
- **Choice**: `aiogram` v3.
- **Rationale**: Built entirely on `asyncio`, type-hinted, strong support for inline keyboards, callback query routing, and support for message replies and chat thread routing.
- **Alternatives considered**: `python-telegram-bot` (good, but `aiogram` v3 offers cleaner async architectural patterns alongside FastAPI).

### Decision 3: Storage & Knowledge Engine — SQLite + ChromaDB / Lexical Fallback
- **Choice**: SQLite for relational state (tickets, users, raw Q&A solutions, timestamps) + ChromaDB (or lightweight embeddings store) for semantic vector search, alongside keyword/fuzzy matching.
- **Rationale**: Self-contained, zero-cost, no mandatory heavy external database cluster required for local or small-to-medium deployments, yet upgradable to PostgreSQL / pgvector if scaled.
- **Alternatives considered**: ElasticSearch (heavy, operational overhead) or pure OpenAI assistants (vendor lock-in, recurring costs).

### Decision 4: Pluggable AI / LLM Layer
- **Choice**: Configurable abstraction layer (`ai_enabled: bool`, supporting OpenAI, Gemini, or local models via unified interface).
- **Rationale**: Directly aligns with the user's preference to work without AI when preferred, falling back to top matching KB solutions, while enabling LLM summarization with zero architectural changes when enabled.
- **Alternatives considered**: Hard-coded LLM requirement (rejected based on user requirement).

### Decision 5: Support Escalation via Telegram Group Replies
- **Choice**: Unresolved questions are published as message cards in a designated `SUPPORT_GROUP_ID`. Support agents reply to that message in Telegram. The bot captures the reply using `reply_to_message`, extracts ticket metadata, relays the answer to the user, and triggers `POST /api/tickets/{id}/resolve`.
- **Rationale**: Eliminates need for custom dashboards; agents operate in the same familiar mobile/desktop Telegram app.
- **Alternatives considered**: Web admin panel (heavier development overhead, slower agent reaction time).

## Architecture Flow

```
+-----------------------------------------------------------------------------------+
|                                  TELEGRAM BOT                                     |
|  (User Chat: /start, question -> Inline Buttons [OUI / NON] -> Ticket Updates)    |
|  (Support Group: Ticket Card -> Agent Reply -> Solution Relay)                   |
+-----------------------------------------------------------------------------------+
                                         │  HTTP / Async Calls
                                         ▼
+-----------------------------------------------------------------------------------+
|                                  BACKEND API                                      |
|                       (FastAPI Orchestrator & Services)                          |
|                                                                                   |
|  +---------------------+   +---------------------+   +--------------------------+ |
|  |   Query Service     |   |   Ticket Service    |   |  Knowledge Base Service  | |
|  +---------------------+   +---------------------+   +--------------------------+ |
+-----------------------------------------------------------------------------------+
             │                                                          │
             ▼                                                          ▼
+--------------------------+                               +------------------------+
|  AI Assistant Service    |                               |    Storage Layer       |
|  (Optional LLM Provider) |                               |  - SQLite (DB)         |
|  - RAG prompt synthesis  |                               |  - ChromaDB (Vectors)  |
+--------------------------+                               +------------------------+
```

## Risks / Trade-offs

- **[Risk] Agent Reply Collisions**: Multiple support agents might reply to the same ticket message in the Telegram group simultaneously.
  - *Mitigation*: The backend enforces an atomic ticket status check (`IN_PROGRESS` / `RESOLVED`). Only the first accepted resolution closes the ticket; subsequent replies notify the agent that the ticket has already been resolved.
- **[Risk] Low Initial KB Coverage**: In a fresh installation, KB searches may yield low confidence scores.
  - *Mitigation*: Threshold-based routing immediately escalates queries with poor matches to the Support Team, accelerating the initial KB population loop.
- **[Risk] Telegram Rate Limits**: High volume of group notifications or user messages could trigger Telegram API rate limits.
  - *Mitigation*: Implement standard backoff and message batching via `aiogram` throttling middleware.

## Migration & Deployment

- System can be executed locally via standard Python virtual environment or packaged with Docker and `docker-compose.yml`.
- `.env` file handles all configurations: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_SUPPORT_GROUP_ID`, `AI_ENABLED`, `AI_API_KEY`, and `DATABASE_URL`.
