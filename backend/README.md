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
10. **Community Group Q&A**: Members ask questions directly in a public community group via `/ask <question>`; the bot answers publicly, tagging the asker, with YES/NO resolution buttons that auto-expire after inactivity. Escalated tickets and all resolution/agent traffic stay confined to the private admin/support group or email — never posted to the community group.
11. **Crypto Market Data**: `/btc`, `/eth`, `/firo`, and other mapped asset commands return live price, 24h change, market cap, and 24h volume from CoinGecko, usable in DM or the community group.
12. **Community Moderation**: Admin-only `/mute`, `/unmute`, `/ban`, `/kick`, and `/warn` commands scoped to the community group, with admin status verified live against the Telegram Bot API. `/purge` lets a community-group admin delete recent bot messages without needing admin-group access.
13. **Dynamic Community Group Setup**: No redeploy needed to point the bot at a community — an env-defined owner (`BOT_OWNER_TELEGRAM_ID`) or an admin they whitelist runs `/setup_community` directly in the target group at any time. The admin/support group stays fixed via `.env` so ticket/moderation traffic can never be redirected by a chat command.
14. **Bilingual Bot (FR/EN)**: All bot-authored messages are available in French (default) and English; the owner or a whitelisted admin switches with `/language fr` or `/language en`.
15. **Next.js Web Frontend**: Dedicated web portal styled with the official **Stack Wallet** graphic charter for natural language knowledge search, ticket escalation, and live tracking.

---

## Project Structure

```
├── backend/                      # Complete Python Backend Services
│   ├── backend/                  # FastAPI Application & Services
│   │   ├── config.py             # Pydantic settings & env resolution
│   │   ├── database.py           # Async SQLAlchemy engine (SQLite / PostgreSQL)
│   │   ├── models.py             # ORM models (Tickets, Knowledge Base, Moderation)
│   │   ├── schemas.py            # Pydantic request/response schemas
│   │   ├── main.py               # FastAPI application & REST endpoints
│   │   └── services/             # Core business logic services
│   ├── bot/                      # Telegram Bot (aiogram 3)
│   │   ├── api_client.py         # Async HTTP client targeting FastAPI
│   │   ├── keyboards.py          # Interactive inline keyboards (YES / NO)
│   │   ├── main.py               # Telegram bot entrypoint
│   │   └── handlers/             # Bot handlers (user, support, community, crypto)
│   ├── alembic/                  # Database schema migration revisions
│   ├── alembic.ini               # Alembic configuration
│   ├── tests/                    # 414 test cases (unit, integration, resilience, E2E)
│   ├── scripts/                  # Management scripts (e.g. seed_knowledge_base.py)
│   ├── data/                     # Persistent storage directory
│   ├── Dockerfile                # Production multi-stage Docker image
│   ├── requirements.txt          # Python dependencies
│   └── pytest.ini                # Pytest configuration
├── frontend/                     # Modern Next.js Web Frontend (NestJS Theme)
│   ├── src/
│   │   ├── app/                  # App Router routes (/, /tickets, /knowledge, /crypto, /settings)
│   │   ├── components/           # UI primitives, layout (FR/EN toggle), cards
│   │   ├── lib/                  # Backend API client, i18n dictionaries
│   │   └── types/                # TypeScript shared models
│   └── package.json              # Next.js 16, React 19, Tailwind CSS
├── deploy/                       # Reverse proxy configurations (Caddy / Nginx)
├── docker-compose.yml            # Multi-service local orchestrator
├── docker-compose.prod.yml       # Production stack with PostgreSQL 16
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

# Your own Telegram user id - message @userinfobot to find it
BOT_OWNER_TELEGRAM_ID=

# Optional: Enable AI Module
AI_ENABLED=false
AI_API_KEY=
AI_PROVIDER=gemini
```

> **Tip to find `TELEGRAM_SUPPORT_GROUP_ID`:**
> 1. Create the admin/support Telegram group and add your bot as a member.
> 2. Send any message in the group, then call `https://api.telegram.org/bot<TOKEN>/getUpdates` to inspect `chat.id` (a negative integer starting with `-100`).

**The community group is not set in `.env`.** Instead, configure it from inside Telegram, at any time, without a redeploy:

1. Start a private chat with the bot as the configured `BOT_OWNER_TELEGRAM_ID` and send `/start` — since no community group is configured yet, the bot replies with a short setup tutorial.
2. Add the bot as an **admin** to the Telegram group you want to use as the community group, with rights to restrict members, ban/unban users, and delete messages — otherwise `/mute`, `/ban`, `/kick`, and `/purge` will fail with a Telegram permission error.
3. In that group, send `/setup_community`. It becomes the active community group immediately.
4. Optionally, as the owner, run `/whitelist add <user_id>` (in DM or the admin group) to let another trusted admin also run `/setup_community` and `/language` — a whitelisted admin cannot manage the whitelist themselves, only the owner can.
5. Optionally, switch the bot's messages to English at any time with `/language en` (or back to French with `/language fr`), run by the owner or a whitelisted admin.

Run `/setup_community` again at any time to point the bot at a different group — it replaces the previous one immediately.

> **Upgrading an existing deployment:** if you already had `TELEGRAM_COMMUNITY_GROUP_ID` set in `.env` before this feature existed, its value is copied into the new persisted setting automatically on first startup after upgrading (and only if no community group has been configured yet). After that one-time copy, the env var is never read again — use `/setup_community` for any further change.

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
cd backend
uvicorn backend.main:app --reload --port 8000

# Terminal 2: Start the Telegram Bot
cd backend
python -m bot.main

# Terminal 3: Start the Next.js Frontend (NestJS theme)
cd frontend
npm install
npm run dev
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

The automated test suite contains **376 tests** across 46 modular test files covering Functional paths, Security (SQLi, XSS, IDOR, auth, log leakage), Robustness (concurrency, external network failures, timeouts, idempotence), community/moderation/crypto command routing, dynamic community-group setup and owner/whitelist access control, FR/EN localization, and multi-layer assertions (HTTP + Database + Logs).

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


