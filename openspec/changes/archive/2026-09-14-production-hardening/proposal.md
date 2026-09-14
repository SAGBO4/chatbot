## Why

Although the chatbot and ticketing backend are functional, tested, and resilient, scaling to a high-volume production environment exposes vulnerabilities to spam abuse, database concurrency bottlenecks, log leakage of webhook secrets, and silent infrastructure failures. Implementing production hardening now guarantees uptime, protects API/LLM quotas, improves multi-agent write concurrency, and provides immediate visibility into operational errors.

## What Changes

- **Rate-Limiting & Anti-Spam (Bot & Backend)**:
  - Add in-memory throttling middleware in Aiogram (e.g. max 5 queries per 10s per Telegram `user_id`).
  - Add rate-limiting on FastAPI public endpoints (`/api/query`, `/api/tickets`) using a lightweight limiter (e.g. `slowapi` or sliding window).
- **PostgreSQL Scalability & Production Storage**:
  - Add official PostgreSQL support alongside SQLite via `asyncpg` (`postgresql+asyncpg://`).
  - Provide production Docker Compose profile with a PostgreSQL 16 container and persistent volume.
  - Verify Alembic migrations and startup schema synchronization compatibility with PostgreSQL.
- **Webhook Security & Proxy Hardening**:
  - Provide standard production reverse-proxy configuration templates (Nginx and Caddy) that disable query parameter logging for `/api/webhooks/email-inbound/brevo` to prevent `BREVO_INBOUND_SECRET` leakage in access logs.
- **Monitoring & Error Alerting**:
  - Integrate Sentry SDK (optional via `SENTRY_DSN` environment variable) in FastAPI lifespan and Aiogram bot error handlers for automatic capture of unhandled exceptions, SMTP delivery errors, and AI provider failures.
  - Expose extended health metrics in `/health` (database connectivity status, memory/process stats, background queue health).

## Capabilities

### New Capabilities
- `monitoring-alerting`: Sentry error capture, application health observability, and failure notifications for both backend and bot services.

### Modified Capabilities
- `telegram-bot`: Add user query throttling and flood control to prevent spam and LLM quota exhaustion.
- `database-migrations`: Support PostgreSQL as first-class database engine with Alembic migration compatibility.
- `email-support`: Harden webhook logging security guidelines and Brevo secret protection behind reverse proxies.

## Impact

- **Affected code**: `backend/main.py`, `backend/config.py`, `backend/database.py`, `bot/handlers/user_handlers.py`, `bot/main.py`, `docker-compose.yml`, `requirements.txt`.
- **Dependencies**: `slowapi`, `asyncpg`, `sentry-sdk` (optional/pluggable).
- **Breaking changes**: None. SQLite and current development workflow remain default when PostgreSQL/Sentry are not configured.
