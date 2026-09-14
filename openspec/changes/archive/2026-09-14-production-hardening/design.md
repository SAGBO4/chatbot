## Context

The chatbot solution combines an Aiogram 3 bot frontend, a FastAPI backend, an asynchronous SQLAlchemy data tier, and integrations with email (Brevo/SMTP) and AI providers. See `proposal.md` for motivation. To transition from a prototype/single-VPS deployment to a production-grade service, the system requires protection against traffic bursts, scalable database concurrency, reverse proxy access log protection, and proactive telemetry.

## Goals / Non-Goals

**Goals:**
- Implement per-user rate limiting on Telegram to stop flood attacks and prevent LLM/server exhaustion.
- Implement rate limiting on FastAPI endpoints (`/api/query`, `/api/tickets`) to defend against unauthenticated or abusive traffic.
- Enable zero-code-change switching to PostgreSQL via `DATABASE_URL=postgresql+asyncpg://...`.
- Add a production Docker Compose setup with PostgreSQL 16 and volume persistence.
- Provide tested reverse proxy configurations (Nginx & Caddy) preventing `?token=` leakage in access logs for Brevo webhooks.
- Provide optional Sentry error tracking and health diagnostics on `/health`.

**Non-Goals:**
- Distributed Redis-backed rate limiting (an in-memory token bucket / sliding window is sufficient for single or paired bot/backend nodes; Redis adds unnecessary deployment overhead at this stage).
- Replacing Alembic or altering existing database table models.
- Rewriting the Telegram Bot UI.

## Decisions

### 1. In-Memory Throttling Middleware in Aiogram
- **Decision**: Implement an Aiogram `BaseMiddleware` tracking message timestamps per `user_id` with a sliding window (default: max 5 messages per 10 seconds).
- **Rationale**: Keeps the bot responsive without introducing external dependencies like Redis. Messages exceeding the limit immediately receive a throttling notice and are dropped before hitting the backend.
- **Alternatives considered**: Redis-based rate limiting (rejected: premature complexity).

### 2. FastAPI Rate Limiting via `slowapi`
- **Decision**: Integrate `slowapi` with in-memory storage, rate-limiting `/api/query` (e.g. 30 requests/minute per client IP or user) and `/api/tickets` (e.g. 10 requests/minute).
- **Rationale**: `slowapi` is the community standard for FastAPI/Starlette, uses `limits`, and supports seamless header decoration (`Retry-After`, `X-RateLimit-*`).
- **Alternatives considered**: Custom Starlette middleware (rejected: reinvents wheel, lacks standard headers).

### 3. Dual Engine Database Abstraction (SQLite & PostgreSQL)
- **Decision**: Support `postgresql+asyncpg://` in `backend/database.py` and `backend/config.py`. Add `asyncpg` to `requirements.txt`.
- **Rationale**: SQLite WAL mode remains default for local tests and lightweight VPS, while PostgreSQL can be enabled simply by supplying a PostgreSQL connection string.
- **SQLite vs Postgres dialect handling**:
  - SQLite PRAGMAs (`WAL`, `busy_timeout`) are executed conditionally only when `"sqlite" in settings.DATABASE_URL`.
  - Postgres connection pool arguments (`pool_size`, `max_overflow`) are applied when using Postgres.
  - Startup migration helper `_add_missing_columns` is compatible with both SQLite and Postgres.

### 4. Reverse Proxy Secret Sanitization (Nginx / Caddy)
- **Decision**: Provide configuration files in a new `deploy/` directory:
  - `deploy/nginx.conf`: Custom log format redacting `$query_string` or logging `$uri` without args on `/api/webhooks/email-inbound/brevo`.
  - `deploy/Caddyfile`: Explicit `log` directive omitting query parameters on the Brevo webhook path.
- **Rationale**: Brevo's Inbound Parsing webhook requires passing authentication via `?token=`. Redacting query parameters in the proxy layer prevents leaking secrets to disk or log management platforms (Datadog, CloudWatch).

### 5. Pluggable Sentry Integration & Diagnostics
- **Decision**: Initialize `sentry_sdk` in `backend/main.py` and `bot/main.py` if `SENTRY_DSN` is set.
- **Rationale**: Zero performance or configuration penalty when `SENTRY_DSN` is unset, but provides immediate exception alerting in production.
- **Diagnostics**: Update `/health` to execute `SELECT 1` and report connectivity status, returning HTTP 503 if the database is unreachable.

## Risks / Trade-offs

- **[Risk] In-memory rate limiting resets on restart** → Mitigation: Acceptable for anti-spam flood protection; restart duration is negligible.
- **[Risk] PostgreSQL driver installation on lightweight environments** → Mitigation: `asyncpg` compiles binary wheels for Linux/Docker, avoiding local build tool dependencies.
- **[Risk] Sentry network overhead on exceptions** → Mitigation: Sentry SDK uses background transport worker threads, non-blocking to request handlers.

## Migration Plan

1. Install updated dependencies (`slowapi`, `asyncpg`, `sentry-sdk`).
2. If transitioning an existing deployment to PostgreSQL:
   - Start postgres service via `docker-compose.yml`.
   - Run `alembic upgrade head` pointing to PostgreSQL.
   - Export SQLite data via dump script if migrating historical tickets.
3. Update reverse proxy using provided `deploy/nginx.conf` or `deploy/Caddyfile`.
