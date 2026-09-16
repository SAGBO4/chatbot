# Telegram Support Bot with Knowledge Base & AI Feedback Loop

This project implements a complete automated support system on Telegram, connected to a FastAPI Backend API, an evolving knowledge base, and a configurable AI module.

---

## System Architecture

```
                    TELEGRAM
                       │
                       ▼
                ┌──────────────┐
                │ Telegram Bot │
                └──────┬───────┘
                       │
                       ▼
                ┌──────────────┐
                │ Backend API  │
                └──────┬───────┘
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
      Knowledge Base       AI (Optional)
             │                   │
             └─────────┬─────────┘
                       ▼
                  User Answer
                       │
                Issue resolved?
                    /       \
                  YES        NO
                   │          │
                   ▼          ▼
                  END       TICKET
                              │
                              ▼
                         SUPPORT TEAM (Telegram Group)
                              │
                              ▼
                         New Solution
                              │
                              ▼
                        Knowledge Base
```

### Key Features:
1. **Automated Telegram Support**: Users ask questions and receive instant answers.
2. **Two-step Confirmation (YES / NO)**: Interactive buttons under each response to validate resolution.
3. **Automatic Escalation (NO)**: Immediate ticket creation and notification in a private Telegram support group.
4. **Resolution via Telegram Reply**: Support agents simply reply to the ticket card message in the group to forward the solution to the user.
5. **Continuous Learning (Feedback Loop)**: Every solution provided by a support agent is automatically indexed into the knowledge base.
6. **Pluggable AI / Zero Extra Cost**: Operates 100% autonomously without AI using lexical/semantic similarity search, or with an LLM (OpenAI, Gemini, DeepSeek) if an API key is configured.
7. **Robust Background Isolation**: Asynchronous email dispatches and Telegram notifications run inside fault-isolated task wrappers, ensuring third-party network drops never crash the HTTP response lifecycle.
8. **IDOR Access Control**: User-scoped ticket retrieval (`?user_id=`) prevents unauthorized cross-user inspection while preserving administrative master access.
9. **Dual-Mode Webhook Security**: Brevo inbound emails authenticate via `X-Webhook-Token` / `X-Brevo-Token` headers or query parameters with automated access log token redaction.

---

## Project Structure

```
├── backend/
│   ├── config.py                 # Pydantic configuration (environment variables)
│   ├── database.py               # Asynchronous SQLAlchemy database engine (SQLite / PostgreSQL)
│   ├── models.py                 # ORM Models (Tickets, Knowledge Base articles)
│   ├── schemas.py                # Pydantic request/response schemas
│   ├── main.py                   # FastAPI application and REST endpoints
│   └── services/
│       ├── knowledge_base.py     # Search engine and KB ingestion service
│       ├── query_orchestrator.py # Query orchestration pipeline
│       ├── ai_assistant.py       # Optional AI module (LLM RAG)
│       ├── email_service.py      # Multi-channel SMTP notifications
│       ├── telegram_relay.py     # Backend-to-Telegram notification relay
│       └── ticket_service.py     # Ticket lifecycle management
├── bot/
│   ├── api_client.py             # Asynchronous HTTP client targeting the backend
│   ├── keyboards.py              # Telegram inline keyboards (YES / NO)
│   ├── main.py                   # Telegram bot entrypoint (aiogram 3)
│   ├── utils.py                  # Markdown escaping and Telegram utilities
│   └── handlers/
│       ├── user_handlers.py      # Handlers for private user chats
│       └── support_handlers.py   # Handlers for the support team group
├── tests/                        # Unit, integration, resilience, and E2E test suite
├── Dockerfile                    # Production-ready Docker container image
├── docker-compose.yml            # Multi-service deployment (backend + bot)
├── requirements.txt              # Python dependencies
└── .env.example                  # Environment variables template
```

---

## Installation & Quick Start

### 1. Clone and Set Up Environment

```bash
# Clone the repository
git clone <repo_url>
cd chatbot

# Create a virtual environment
virtualenv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy configuration template
cp .env.example .env
```

### 2. Configure the `.env` File

Edit the `.env` file with your Telegram bot credentials:
```ini
TELEGRAM_BOT_TOKEN=
TELEGRAM_SUPPORT_GROUP_ID=

# Optional: Enable AI Module
AI_ENABLED=false
AI_API_KEY=
AI_PROVIDER=gemini
```

> **Tip to find your `TELEGRAM_SUPPORT_GROUP_ID`:**
> 1. Create a Telegram group for your support team and add your bot as a member.
> 2. Send any message in the group, then call `https://api.telegram.org/bot<TOKEN>/getUpdates` to inspect `chat.id` (a negative integer starting with `-100`).

### 3. Database Migrations & Initial Data Seeding

Apply database schema migrations using Alembic:
```bash
alembic upgrade head
```

Seed the knowledge base with initial Stack Wallet bilingual FAQs:
```bash
python -m scripts.seed_knowledge_base
```

### 4. Optional: Inbound Email Webhooks (Brevo & HMAC Relay)

To resolve tickets via email replies:
- **Brevo Inbound Parsing**: Point your Brevo inbound webhook to `https://your-domain.com/api/webhooks/email-inbound/brevo`.
  - Supports header authentication via `X-Webhook-Token: <BREVO_INBOUND_SECRET>` or `X-Brevo-Token` to eliminate secrets from URLs.
  - Supports backward-compatible query parameter `?token=<BREVO_INBOUND_SECRET>` with automated in-app log redaction.
- **HMAC Email Relay**: Send signed payloads to `/api/webhooks/email-inbound` with `EMAIL_WEBHOOK_SECRET` and header `X-Webhook-Signature: <sha256_hex>`.
- Restrict authorized responder addresses via `ALLOWED_SUPPORT_EMAIL_SENDERS`.

### 5. Launch Services

#### Local Development Mode:
```bash
# Terminal 1: Start the backend API
uvicorn backend.main:app --reload --port 8000

# Terminal 2: Start the Telegram Bot
python -m bot.main
```

#### Docker Compose Mode (Default SQLite WAL):
```bash
docker compose up --build -d
```

#### Docker Compose Mode (Production PostgreSQL 16):
For high-volume production deployments with multiple concurrent support agents, use the dedicated PostgreSQL stack:
```bash
docker compose -f docker-compose.prod.yml up --build -d
```

### 6. Production Reverse Proxy & Webhook Hardening

To safeguard credentials passed via webhooks:
- **Application Level**: The backend includes `SensitiveDataFilter` and `sanitize_access_logging_middleware` which automatically redact sensitive parameters (`?token=[REDACTED]`, `?api_key=[REDACTED]`) from server traces and access logs.
- **Nginx**: Use the template provided in [deploy/nginx.conf](deploy/nginx.conf) with custom log format `redacted_combined` logging `$uri` without query strings.
- **Caddy**: Use the template provided in [deploy/Caddyfile](deploy/Caddyfile) with the `format filter` log directive.

### 7. Production Monitoring & Anti-Spam Rate Limiting

- **Rate Limiting**:
  - Telegram Bot messages are throttled via an in-memory sliding window (5 messages / 10s per `user_id`).
  - FastAPI endpoints `/api/query` (30 req/min) and `/api/tickets` (10 req/min) are protected against floods.
- **Diagnostics & Health**:
  - Endpoint `GET /health` runs an active `SELECT 1` ping against the database and returns HTTP 503 if unreachable.
- **Sentry Integration**:
  - Set `SENTRY_DSN=https://...` in `.env` to automatically capture unhandled exceptions with full tracebacks.

### 8. User Ownership & IDOR Protection

- `GET /api/tickets` accepts an optional `user_id` query parameter to scope listings strictly to that user's tickets.
- `GET /api/tickets/{ticket_id}` accepts an optional `user_id` query parameter; querying a ticket belonging to another user returns `404 Not Found`.
- Administrative requests without `user_id` require `X-API-Key` and have full visibility for bot operations.

---

## Testing & Verification

The automated test suite contains **238 tests** across 11 modular suites covering Functional paths, Security (SQLi, XSS, IDOR, auth, log leakage), Robustness (concurrency, external network failures, timeouts, idempotence), and multi-layer assertions (HTTP + Database + Logs).

All tests run hermetically using isolated SQLite databases and mock external boundaries (Brevo SMTP and Telegram Bot API) to guarantee safety, zero external network leaks, and rapid execution (~16s):

```bash
# Run all tests
pytest -v

# Run with module coverage report (HTML report + >=85% threshold check)
pytest --cov=backend --cov=bot --cov-report=html --cov-fail-under=85

# Mutation testing (verifies that tests actively catch seeded bugs)
mutmut run

# Static security analysis & linting
bandit -r backend/ bot/                 # Python AST security linter (0 issues)
semgrep scan --config=auto backend/ bot/ # Semantic AST multi-rule security analysis (0 issues)
trivy fs --file-patterns "pip:requirements.lock" requirements.lock # Dependency vulnerabilities & secret scanning (0 issues)
pip-audit                               # PyPA advisory vulnerability scanner (0 issues)
```


