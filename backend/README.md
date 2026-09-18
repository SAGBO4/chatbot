<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../frontend/public/stack-logo-white.png">
    <source media="(prefers-color-scheme: light)" srcset="../frontend/public/stack-logo-full.png">
    <img alt="Stack Wallet" src="../frontend/public/stack-logo-full.png" width="260" valign="middle">
  </picture>
  &nbsp;&nbsp;&nbsp;
  <img src="../frontend/public/stack-wallet-bot.png" width="100" alt="Stack Wallet Bot" valign="middle">
</p>

# Backend — API, Telegram Bot & Infrastructure

FastAPI backend, Telegram bot (aiogram 3), and supporting infrastructure for the [Telegram Support Bot](../README.md) project. See the [root README](../README.md) for the product overview, architecture diagram, and feature list.

---

## Structure

```
backend/
├── backend/              # FastAPI Application & Services (the importable `backend` package)
│   ├── config.py         # Pydantic settings & env resolution
│   ├── database.py       # Async SQLAlchemy engine (SQLite / PostgreSQL)
│   ├── models.py         # ORM models (Tickets, Knowledge Base, Moderation)
│   ├── schemas.py        # Pydantic request/response schemas
│   ├── main.py           # FastAPI application & REST endpoints
│   └── services/         # Core business logic services
├── bot/                   # Telegram Bot (aiogram 3)
│   ├── api_client.py     # Async HTTP client targeting FastAPI
│   ├── keyboards.py      # Interactive inline keyboards (YES / NO)
│   ├── main.py           # Telegram bot entrypoint
│   └── handlers/         # Bot handlers (user, support, community, crypto)
├── alembic/               # Database schema migration revisions
├── alembic.ini            # Alembic configuration
├── tests/                 # 414 test cases (unit, integration, resilience, E2E)
├── scripts/               # Management scripts (e.g. seed_knowledge_base.py)
├── data/                  # Persistent storage directory
├── deploy/                # Reverse proxy configurations (Caddy / Nginx)
├── Dockerfile             # Production multi-stage Docker image
├── docker-compose.yml     # Multi-service local orchestrator
├── docker-compose.prod.yml # Production stack with PostgreSQL 16
├── requirements.txt       # Python dependencies
└── pytest.ini             # Pytest configuration
```

> **Note:** the project root is `backend/`, and the importable Python package is the nested `backend/backend/` — that's why `backend.main:app` (see the Dockerfile `CMD` and the `uvicorn` command below) resolves from inside this directory. It's an intentional (if slightly confusing) src-style layout, not a duplicate folder.

---

## 1. Environment Setup

```bash
# Create a virtual environment
virtualenv .venv
source .venv/bin/activate

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Copy configuration template
cp .env.example .env
```

## 2. Configure the `.env` File

Edit `backend/.env` with your Telegram bot credentials:
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

## 3. Database Migrations & Initial Data Seeding

From the `backend/` directory:

```bash
cd backend

# Apply database schema migrations using Alembic
alembic upgrade head

# Seed the knowledge base with initial Stack Wallet bilingual FAQs
python -m scripts.seed_knowledge_base
```

## 4. Optional: Inbound Email Webhooks (Brevo & HMAC Relay)

To resolve tickets via email replies:
- **Brevo Inbound Parsing**: Point your Brevo inbound webhook to `https://your-domain.com/api/webhooks/email-inbound/brevo`.
  - Supports header authentication via `X-Webhook-Token: <BREVO_INBOUND_SECRET>` or `X-Brevo-Token` to eliminate secrets from URLs.
  - Supports backward-compatible query parameter `?token=<BREVO_INBOUND_SECRET>` with automated in-app log redaction.
- **HMAC Email Relay**: Send signed payloads to `/api/webhooks/email-inbound` with `EMAIL_WEBHOOK_SECRET` and header `X-Webhook-Signature: <sha256_hex>`.
- Restrict authorized responder addresses via `ALLOWED_SUPPORT_EMAIL_SENDERS`.

## 5. Launch Services

#### Local Development Mode:
```bash
# Terminal 1: Start the backend API
cd backend
uvicorn backend.main:app --reload --port 8000

# Terminal 2: Start the Telegram Bot
cd backend
python -m bot.main
```

For the Next.js frontend, see [frontend/README.md](../frontend/README.md).

#### Docker Compose Mode (Default SQLite WAL):
```bash
cd backend
docker compose up --build -d
```

#### Docker Compose Mode (Production PostgreSQL 16):
For high-volume production deployments with multiple concurrent support agents, use the dedicated PostgreSQL stack:
```bash
cd backend
docker compose -f docker-compose.prod.yml up --build -d
```

## 6. Production Reverse Proxy & Webhook Hardening

To safeguard credentials passed via webhooks:
- **Application Level**: The backend includes `SensitiveDataFilter` and `sanitize_access_logging_middleware` which automatically redact sensitive parameters (`?token=[REDACTED]`, `?api_key=[REDACTED]`) from server traces and access logs.
- **Nginx**: Use the template provided in [backend/deploy/nginx.conf](deploy/nginx.conf) with custom log format `redacted_combined` logging `$uri` without query strings.
- **Caddy**: Use the template provided in [backend/deploy/Caddyfile](deploy/Caddyfile) with the `format filter` log directive.

## 7. Production Monitoring & Anti-Spam Rate Limiting

- **Rate Limiting**:
  - Telegram Bot messages are throttled via an in-memory sliding window (5 messages / 10s per `user_id`).
  - FastAPI endpoints `/api/query` (30 req/min) and `/api/tickets` (10 req/min) are protected against floods.
- **Diagnostics & Health**:
  - Endpoint `GET /health` runs an active `SELECT 1` ping against the database and returns HTTP 503 if unreachable.
- **Sentry Integration**:
  - Set `SENTRY_DSN=https://...` in `.env` to automatically capture unhandled exceptions with full tracebacks.

## 8. User Ownership & IDOR Protection

- `GET /api/tickets` accepts an optional `user_id` query parameter to scope listings strictly to that user's tickets.
- `GET /api/tickets/{ticket_id}` accepts an optional `user_id` query parameter; querying a ticket belonging to another user returns `404 Not Found`.
- Administrative requests without `user_id` require `X-API-Key` and have full visibility for bot operations.

---

## Testing & Verification

The automated test suite contains **414 tests** across modular test files covering Functional paths, Security (SQLi, XSS, IDOR, auth, log leakage), Robustness (concurrency, external network failures, timeouts, idempotence), community/moderation/crypto command routing, dynamic community-group setup and owner/whitelist access control, FR/EN localization, and multi-layer assertions (HTTP + Database + Logs).

All tests run hermetically using isolated SQLite databases and mock external boundaries (Brevo SMTP and Telegram Bot API) to guarantee safety, zero external network leaks, and rapid execution (~16s):

```bash
cd backend

# Run all 414 tests
pytest -v

# Run with module coverage report (HTML report + >=85% threshold check)
pytest --cov=backend --cov=bot --cov-report=html --cov-fail-under=85

# Mutation testing (verifies that tests actively catch seeded bugs)
mutmut run

# Static security analysis & linting
ruff check .
bandit -r backend/ bot/                 # Python AST security linter (0 issues)
semgrep scan --config=auto backend/ bot/ # Semantic AST multi-rule security analysis (0 issues)
trivy fs --file-patterns "pip:requirements.lock" requirements.lock # Dependency vulnerabilities & secret scanning (0 issues)
pip-audit                               # PyPA advisory vulnerability scanner (0 issues)
```
