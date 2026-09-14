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
- **Brevo Inbound Parsing**: Point your Brevo inbound webhook to `https://your-domain.com/api/webhooks/email-inbound/brevo?token=YOUR_BREVO_SECRET` with `BREVO_INBOUND_SECRET` configured in `.env`.
- **HMAC Email Relay**: Send signed payloads to `/api/webhooks/email-inbound` with `EMAIL_WEBHOOK_SECRET` and header `X-Webhook-Signature: <sha256_hex>`.
- Optionally restrict accepted responder addresses via `ALLOWED_SUPPORT_EMAIL_SENDERS`.

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

When deploying behind a reverse proxy (Nginx or Caddy), sensitive URL query parameters (such as `?token=` on Brevo inbound webhooks) should be redacted from access logs to prevent token leakage:
- **Nginx**: Use the template provided in [deploy/nginx.conf](deploy/nginx.conf) with custom log format `redacted_combined`.
- **Caddy**: Use the template provided in [deploy/Caddyfile](deploy/Caddyfile) with the `format filter` log directive.

### 7. Production Monitoring & Anti-Spam Rate Limiting

- **Rate Limiting**:
  - Telegram Bot messages are throttled via an in-memory sliding window (5 messages / 10s per `user_id`).
  - FastAPI endpoints `/api/query` (30 req/min) and `/api/tickets` (10 req/min) are protected against floods.
- **Diagnostics & Health**:
  - Endpoint `GET /health` runs an active `SELECT 1` ping against the database and returns HTTP 503 if unreachable.
- **Sentry Integration**:
  - Set `SENTRY_DSN=https://...` in `.env` to automatically capture unhandled exceptions with full tracebacks.

---

## Testing & Verification

The automated test suite covers unit tests, database migrations, API endpoints, rate limiting, LLM resilience, and the full end-to-end (E2E) lifecycle loop:

```bash
pytest -v
```

