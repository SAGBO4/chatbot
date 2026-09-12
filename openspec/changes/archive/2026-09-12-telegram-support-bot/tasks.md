## 1. Project Scaffolding & Configuration

- [x] 1.1 Create project directory structure (`backend/`, `bot/`, `tests/`), dependency manifest (`requirements.txt`), and `.env.example`. Verify by confirming files exist and `pip install -r requirements.txt` succeeds.
- [x] 1.2 Implement configuration loader using Pydantic Settings for environment variables (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_SUPPORT_GROUP_ID`, `DATABASE_URL`, `AI_ENABLED`, `AI_API_KEY`). Verify with a test checking configuration defaults and overrides.

## 2. Database & Knowledge Base Engine

- [x] 2.1 Define SQLite database models with SQLAlchemy for tickets (`id`, `user_id`, `question`, `status`, `solution`, `created_at`, `resolved_at`) and knowledge base articles (`id`, `question`, `solution`, `keywords`, `created_at`). Verify by running database initialization test.
- [x] 2.2 Implement Knowledge Base repository service supporting document insertion, lexical search, and vector similarity indexing (ChromaDB / lightweight embeddings). Verify search ranking and article retrieval with unit tests.
- [x] 2.3 Implement the dynamic ingestion function that indexes newly approved question-solution pairs into the Knowledge Base. Verify ingestion and immediate retrieval through an integration test.

## 3. Backend API & Query Pipeline

- [x] 3.1 Implement core query orchestration (`POST /api/query`) that searches the Knowledge Base, evaluates confidence score, and returns solution content. Verify response format and empty result handling with unit tests.
- [x] 3.2 Implement pluggable AI assistant service that synthesizes context-grounded answers when `AI_ENABLED=true` and seamlessly bypasses synthesis when `AI_ENABLED=false`. Verify behavior across both states using mock unit tests.
- [x] 3.3 Implement Ticket management endpoints (`POST /api/tickets`, `GET /api/tickets/{id}`, `POST /api/tickets/{id}/resolve`) that manage ticket states and trigger Knowledge Base ingestion upon resolution. Verify state transitions and trigger logic with API tests.

## 4. Telegram Bot Integration

- [x] 4.1 Implement `aiogram` user message handlers for `/start`, text questions, and sending automated answers. Verify handler registration and message delivery using mock bot harness.
- [x] 4.2 Implement inline keyboard for resolution feedback ("Problème résolu ? OUI / NON") and callback handlers that close resolved inquiries on "OUI" and trigger ticket escalation on "NON". Verify callback query handling with tests.
- [x] 4.3 Implement Telegram Support Group routing that posts ticket cards with details to `TELEGRAM_SUPPORT_GROUP_ID` and captures agent replies using `reply_to_message` to transmit answers back to the user. Verify agent reply parsing and routing with tests.

## 5. End-to-End Testing & Packaging

- [x] 5.1 Implement full end-to-end integration test simulating the entire loop: user query -> no resolution ("NON") -> ticket escalated to support -> agent replies with new solution -> user receives solution -> solution ingested into KB -> repeat query answered automatically. Verify test suite passes with `pytest`.
- [x] 5.2 Provide Dockerfile, `docker-compose.yml`, and `README.md` with setup and operational instructions. Verify container build succeeds.
