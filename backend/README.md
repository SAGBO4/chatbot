<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../frontend/public/stack-logo-white.png">
  <source media="(prefers-color-scheme: light)" srcset="../frontend/public/stack-logo-full.png">
  <img alt="Stack Wallet" src="../frontend/public/stack-logo-full.png" width="260">
</picture>

<h1><img src="../frontend/public/stack-wallet-bot.png" width="54" alt="Stack Wallet Bot" valign="middle"> Backend — API, Telegram Bot & Infrastructure</h1>

FastAPI backend, Telegram bot (aiogram 3), and supporting infrastructure for the [Telegram Support Bot](../README.md) project. See the [root README](../README.md) for the product overview, architecture diagram, and feature list.

---

## Structure

```
backend/
├── app/                  # FastAPI Application & Services
│   ├── main.py           # App wiring only: lifespan, middleware, includes the routers
│   ├── routers/          # REST endpoints, one module per area (tickets, query, webhooks, ...)
│   ├── services/         # Core business logic services
│   ├── config.py         # Pydantic settings & env resolution
│   ├── database.py       # Async SQLAlchemy engine (SQLite / PostgreSQL), Alembic at startup
│   ├── models.py         # ORM models (Tickets, Knowledge Base, Moderation)
│   ├── schemas.py        # Pydantic request/response schemas
│   ├── security.py       # API key and webhook authentication
│   ├── inbound_email.py  # Turns an inbound email into a ticket resolution
│   ├── email_parsing.py  # Ticket id in subjects, quoted-reply stripping
│   ├── background.py     # Fire-and-forget tasks whose failures are logged
│   ├── observability.py  # Sentry setup, secret redaction in logs and events
│   ├── i18n.py           # fr / en message table, shared by the API and the bot
│   ├── telegram_text.py  # Markdown escaping and truncation for Telegram
│   └── limiter.py        # Rate limiting (slowapi)
├── bot/                   # Telegram Bot (aiogram 3); never imported by app/
│   ├── main.py           # Telegram bot entrypoint
│   ├── api_client.py     # Async HTTP client targeting FastAPI
│   ├── keyboards.py      # Interactive inline keyboards (YES / NO)
│   ├── messaging.py      # Send with a plain-text fallback when Markdown is rejected
│   ├── ttl_cache.py      # Small expiring cache used by the bot
│   ├── access_control.py, admin_check.py, group_scope.py, language.py, ticket_escalation.py
│   ├── middlewares/      # Throttling
│   └── handlers/         # Bot handlers (user, support, community, moderation, crypto)
├── alembic/               # Database schema migration revisions
├── alembic.ini            # Alembic configuration
├── tests/                 # 500+ test cases (unit, integration, resilience, E2E)
├── scripts/               # Management scripts (e.g. seed_knowledge_base.py)
├── data/                  # Persistent storage directory
├── deploy/                # Reverse proxy configurations (Caddy / Nginx)
├── Dockerfile             # Docker image for the API and the bot (non-root user)
├── Procfile, CHECKS       # Process types and health check for Dokku / Heroku-style platforms
├── docker-compose.yml     # Multi-service local orchestrator
├── docker-compose.prod.yml # Production stack with PostgreSQL 16
├── requirements.txt       # Runtime dependencies
├── requirements-dev.txt   # Test and QA tools (pytest, ruff, bandit, semgrep, ...)
├── requirements.lock      # Pinned runtime set installed by the Docker image
└── pytest.ini             # Pytest configuration
```

---

## 1. Environment Setup

```bash
# Create a virtual environment
virtualenv .venv
source .venv/bin/activate

# Install backend dependencies
cd backend
pip install -r requirements-dev.txt   # runtime dependencies + the test and QA tools

# Copy configuration template (defined once at the repo root)
cp ../.env.example .env
```

## 2. Configure the `.env` File

Edit `backend/.env` with your Telegram bot credentials:
```ini
TELEGRAM_BOT_TOKEN=
TELEGRAM_SUPPORT_GROUP_ID=

# Your own Telegram user id - message @userinfobot to find it
BOT_OWNER_TELEGRAM_ID=

# Shared secret between the backend and the bot (see the note below)
API_KEY=

# Optional: Enable AI Module
AI_ENABLED=false
AI_API_KEY=
AI_PROVIDER=gemini
```

> **Tip to find `TELEGRAM_SUPPORT_GROUP_ID`:**
> 1. Create the admin/support Telegram group and add your bot as a member.
> 2. Send any message in the group, then call `https://api.telegram.org/bot<TOKEN>/getUpdates` to inspect `chat.id` (a negative integer starting with `-100`).

> **`API_KEY` is required.** The backend refuses every `/api/*` request with `503 Backend API is not configured (API_KEY missing)` until it is set — this is deliberate (fail-closed), not a bug. Generate a long random value with `openssl rand -hex 32`, use a different one per environment, and set the same value wherever the bot runs: it sends it as the `X-API-Key` header.

**The community group is not set in `.env`.** Instead, configure it from inside Telegram, at any time, without a redeploy:

1. Start a private chat with the bot as the configured `BOT_OWNER_TELEGRAM_ID` and send `/start` — since no community group is configured yet, the bot replies with a short setup tutorial.
2. Add the bot as an **admin** to the Telegram group you want to use as the community group, with rights to restrict members, ban/unban users, and delete messages — otherwise `/mute`, `/ban`, `/kick`, and `/purge` will fail with a Telegram permission error.
3. In that group, send `/setup_community`. It becomes the active community group immediately.
4. Optionally, as the owner, run `/whitelist add <user_id>` (in DM or the admin group) to let another trusted admin also run `/setup_community` and `/language`, moderate the community group, `/purge`, and resolve support tickets — even without native Telegram admin rights in those groups. A whitelisted admin cannot manage the whitelist themselves, only the owner can.
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
uvicorn app.main:app --reload --port 8000

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
For high-volume production deployments with multiple concurrent support agents, use the dedicated PostgreSQL stack. Set `POSTGRES_PASSWORD` in `backend/.env` first (URL-safe characters only, e.g. `openssl rand -hex 24`): there is no default, and the stack refuses to start without it.
```bash
cd backend
docker compose -f docker-compose.prod.yml up --build -d
```
The API is published on `127.0.0.1:8000` only, so put the reverse proxy described in the next section in front of it; that is also what keeps secrets out of the access logs.

#### Dokku and other Heroku-style platforms:
`Procfile` declares two processes, `web` (the API, on `$PORT`) and `bot` (the Telegram bot), and `CHECKS` points the platform's health check at `/health`. A `DATABASE_URL` written as `postgres://` or `postgresql://` is accepted and rewritten to the `postgresql+asyncpg://` form the async driver needs.

## 6. Production Reverse Proxy & Webhook Hardening

To safeguard credentials passed via webhooks:
- **Application Level**: The backend includes `SensitiveDataFilter` and `sanitize_access_logging_middleware` which automatically redact sensitive parameters (`?token=[REDACTED]`, `?api_key=[REDACTED]`) from server traces and access logs.
- **Nginx**: Use the template provided in [backend/deploy/nginx.conf](deploy/nginx.conf) with custom log format `redacted_combined` logging `$uri` without query strings.
- **Caddy**: Use the template provided in [backend/deploy/Caddyfile](deploy/Caddyfile): its `format filter` log directive redacts the `token`, `secret`, `api_key` and `password` query parameters and the `X-Webhook-Token`, `X-Brevo-Token` and `X-Api-Key` headers (Caddy only masks `Authorization` and `Cookie` by default).

## 7. Production Monitoring & Anti-Spam Rate Limiting

- **Rate Limiting**:
  - Telegram Bot messages are throttled via an in-memory sliding window (5 messages / 10s per `user_id`).
  - FastAPI endpoints `/api/query` (30 req/min) and `/api/tickets` (10 req/min) are protected against floods.
- **Diagnostics & Health**:
  - Endpoint `GET /health` runs an active `SELECT 1` ping against the database and returns HTTP 503 if unreachable.
- **Sentry Integration**:
  - Set `SENTRY_DSN=https://...` in `.env` to automatically capture unhandled exceptions with full tracebacks. `SENTRY_TRACES_SAMPLE_RATE` (0 to 1, default 1.0) sets the share of requests traced; lower it on a busy deployment.
  - Bot tokens and secret query parameters are redacted from logs and from what is sent to Sentry.

## 8. User Ownership & IDOR Protection

- `GET /api/tickets` accepts an optional `user_id` query parameter to scope listings strictly to that user's tickets.
- `GET /api/tickets/{ticket_id}` accepts an optional `user_id` query parameter; querying a ticket belonging to another user returns `404 Not Found`.
- Administrative requests without `user_id` require `X-API-Key` and have full visibility for bot operations.

---

## Testing & Verification

The automated test suite contains **500+ tests** across modular test files covering Functional paths, Security (SQLi, XSS, IDOR, auth, log leakage), Robustness (concurrency, external network failures, timeouts, idempotence), community/moderation/crypto command routing, dynamic community-group setup and owner/whitelist access control, FR/EN localization, and multi-layer assertions (HTTP + Database + Logs).

All tests run hermetically using isolated SQLite databases and mock external boundaries (Brevo SMTP and Telegram Bot API) to guarantee safety, zero external network leaks, and rapid execution (about 10 seconds):

```bash
cd backend

# Run all tests
pytest -v

# Run with module coverage report (HTML report + >=85% threshold check)
pytest --cov=app --cov=bot --cov-report=html --cov-fail-under=85   # about 93% today

# Mutation testing (verifies that tests actively catch seeded bugs)
mutmut run

# Static security analysis & linting
ruff check .
bandit -r app/ bot/                     # Python AST security linter (0 issues)
semgrep scan --config=auto app/ bot/     # Semantic AST multi-rule security analysis
trivy fs --file-patterns "pip:requirements.lock" requirements.lock # Dependency vulnerabilities & secret scanning
pip-audit                               # PyPA advisory vulnerability scanner (0 issues)
```
